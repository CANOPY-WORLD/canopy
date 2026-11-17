"""Physics4D Yi Qi temperature kernels, separated from scene extraction/plotting.

Numerical equations retained; added an optional cooperative cancellation callback.
Source extraction and original hash are recorded in docs/framework/temperature-extraction.json.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

@dataclass(frozen=True)
class Temperature3DScenarioConfig:
    frame_duration_s: float = 1.0
    max_courant: float = .15
    diffusion_coeff_m2_s: float = .01
    velocity_scale: float = 1.0
    temperature_solver_device: str = "cpu"
    on_substep: object = None

@dataclass(frozen=True)
class SouthKensingtonConfig:
    model_resolution_m: float = 1.0
    height_scale_m: float = 1.0

def shift_with_edge(field: np.ndarray, axis: int, step: int) -> np.ndarray:
    shifted = np.roll(field, step, axis=axis)
    if step > 0:
        index = [slice(None)] * field.ndim
        index[axis] = slice(0, step)
        edge_slice = np.take(field, indices=[0], axis=axis)
        shifted[tuple(index)] = edge_slice
    elif step < 0:
        index = [slice(None)] * field.ndim
        index[axis] = slice(step, None)
        edge_slice = np.take(field, indices=[field.shape[axis] - 1], axis=axis)
        shifted[tuple(index)] = edge_slice
    return shifted


def impose_boundary_conditions_3d(
    temperature_c: np.ndarray,
    fields: dict[str, np.ndarray],
    boundary_fields: dict[str, np.ndarray],
    velocity_config: SouthKensingtonConfig,
    temp3d_config: Temperature3DScenarioConfig,
    current_ambient_temp_c: float,
    current_inflow_temp_c: float,
) -> None:
    solid_mask = fields["solid_mask_3d"]
    study_area_3d = np.broadcast_to(fields["study_area_mask_2d"][None, :, :], temperature_c.shape)
    fluid_mask = (~solid_mask) & study_area_3d

    current_solid_temperature_3d = np.full(temperature_c.shape, current_ambient_temp_c, dtype=np.float32)
    current_solid_temperature_3d[fields["roof_mask_3d"]] = (
        current_ambient_temp_c + boundary_fields["roof_surface_temperature_excess_3d"][fields["roof_mask_3d"]]
    )
    temperature_c[solid_mask] = current_solid_temperature_3d[solid_mask]

    left_fluid = fluid_mask[:, :, 0]
    vertical_profile = np.linspace(
        current_inflow_temp_c + 0.1,
        current_inflow_temp_c - 0.1,
        temperature_c.shape[0],
        dtype=np.float32,
    )[:, None]
    temperature_c[:, :, 0][left_fluid] = np.broadcast_to(vertical_profile, temperature_c[:, :, 0].shape)[left_fluid]

    temperature_c[:, :, -1] = np.where(fluid_mask[:, :, -1], temperature_c[:, :, -2], temperature_c[:, :, -1])
    temperature_c[:, 0, :] = np.where(fluid_mask[:, 0, :], temperature_c[:, 1, :], temperature_c[:, 0, :])
    temperature_c[:, -1, :] = np.where(fluid_mask[:, -1, :], temperature_c[:, -2, :], temperature_c[:, -1, :])
    temperature_c[-1, :, :] = np.where(fluid_mask[-1, :, :], current_ambient_temp_c, temperature_c[-1, :, :])
    outside_mask = ~study_area_3d
    temperature_c[outside_mask] = current_ambient_temp_c


def solve_temperature_fields_3d_numpy(
    fields: dict[str, np.ndarray],
    boundary_fields: dict[str, np.ndarray],
    velocity_config: SouthKensingtonConfig,
    temp3d_config: Temperature3DScenarioConfig,
) -> dict[str, object]:
    u_frames = temp3d_config.velocity_scale * fields["u"]
    v_frames = temp3d_config.velocity_scale * fields["v"]
    w_frames = temp3d_config.velocity_scale * fields["w"]
    solid_mask = fields["solid_mask_3d"]
    study_area_3d = np.broadcast_to(fields["study_area_mask_2d"][None, :, :], solid_mask.shape)
    fluid_mask = (~solid_mask) & study_area_3d

    dx = float(velocity_config.model_resolution_m)
    dy = dx
    dz = float(velocity_config.height_scale_m)

    max_speed = float(np.max(np.sqrt(u_frames**2 + v_frames**2 + w_frames**2)))
    stable_dt = temp3d_config.max_courant * min(dx, dy, dz) / max(max_speed, 1e-6)
    diffusion_dt = 0.18 * min(dx, dy, dz) ** 2 / max(temp3d_config.diffusion_coeff_m2_s, 1e-6)
    dt = min(stable_dt, diffusion_dt, temp3d_config.frame_duration_s)
    substeps = max(1, int(math.ceil(temp3d_config.frame_duration_s / max(dt, 1e-6))))
    dt = temp3d_config.frame_duration_s / substeps
    bottom_exchange_coeff = boundary_fields["surface_exchange_coeff_per_s"].astype(np.float32)
    surface_forcing_layer_count = int(boundary_fields["surface_forcing_layer_count"][0])
    ambient_temp_series_c = boundary_fields["ambient_temp_series_c"].astype(np.float32)
    inflow_temp_series_c = boundary_fields["inflow_temp_series_c"].astype(np.float32)

    temperature_c = np.full(solid_mask.shape, float(ambient_temp_series_c[0]), dtype=np.float32)
    impose_boundary_conditions_3d(
        temperature_c,
        fields,
        boundary_fields,
        velocity_config,
        temp3d_config,
        current_ambient_temp_c=float(ambient_temp_series_c[0]),
        current_inflow_temp_c=float(inflow_temp_series_c[0]),
    )

    frames = [temperature_c.copy()]
    frame_means = [float(np.mean(temperature_c[fluid_mask]))]

    for frame_idx in range(u_frames.shape[0]):
        u = np.where(fluid_mask, u_frames[frame_idx], 0.0)
        v = np.where(fluid_mask, v_frames[frame_idx], 0.0)
        w = np.where(fluid_mask, w_frames[frame_idx], 0.0)
        current_ambient_temp_c = float(ambient_temp_series_c[min(frame_idx + 1, ambient_temp_series_c.shape[0] - 1)])
        current_inflow_temp_c = float(inflow_temp_series_c[min(frame_idx + 1, inflow_temp_series_c.shape[0] - 1)])
        current_ground_surface_temperature_c = (
            current_ambient_temp_c + boundary_fields["ground_surface_temperature_excess_c"]
        ).astype(np.float32)

        for _ in range(substeps):
            if temp3d_config.on_substep is not None: temp3d_config.on_substep()
            left = shift_with_edge(temperature_c, axis=2, step=1)
            right = shift_with_edge(temperature_c, axis=2, step=-1)
            north = shift_with_edge(temperature_c, axis=1, step=1)
            south = shift_with_edge(temperature_c, axis=1, step=-1)
            below = shift_with_edge(temperature_c, axis=0, step=1)
            above = shift_with_edge(temperature_c, axis=0, step=-1)
            below[0, :, :] = temperature_c[0, :, :]

            dtdx_backward = (temperature_c - left) / dx
            dtdx_forward = (right - temperature_c) / dx
            dtdy_backward = (temperature_c - north) / dy
            dtdy_forward = (south - temperature_c) / dy
            dtdz_backward = (temperature_c - below) / dz
            dtdz_forward = (above - temperature_c) / dz

            adv_x = np.where(u >= 0.0, u * dtdx_backward, u * dtdx_forward)
            adv_y = np.where(v >= 0.0, v * dtdy_backward, v * dtdy_forward)
            adv_z = np.where(w >= 0.0, w * dtdz_backward, w * dtdz_forward)
            laplacian = (
                (left - 2.0 * temperature_c + right) / (dx**2)
                + (north - 2.0 * temperature_c + south) / (dy**2)
                + (below - 2.0 * temperature_c + above) / (dz**2)
            )
            surface_exchange_term = np.zeros_like(temperature_c, dtype=np.float32)
            bottom_fluid = fluid_mask[0]
            for layer_idx in range(surface_forcing_layer_count):
                layer_fluid = fluid_mask[layer_idx] & bottom_fluid
                surface_exchange_term[layer_idx, layer_fluid] = (
                    bottom_exchange_coeff[layer_fluid]
                    * (
                        current_ground_surface_temperature_c[layer_fluid]
                        - temperature_c[layer_idx, layer_fluid]
                    )
                )

            next_temperature = temperature_c + dt * (
                -(adv_x + adv_y + adv_z)
                + temp3d_config.diffusion_coeff_m2_s * laplacian
                + surface_exchange_term
            )
            temperature_c[fluid_mask] = next_temperature[fluid_mask]
            impose_boundary_conditions_3d(
                temperature_c,
                fields,
                boundary_fields,
                velocity_config,
                temp3d_config,
                current_ambient_temp_c=current_ambient_temp_c,
                current_inflow_temp_c=current_inflow_temp_c,
            )

        frames.append(temperature_c.copy())
        frame_means.append(float(np.mean(temperature_c[fluid_mask])))

    temperature_array = np.stack(frames, axis=0)
    masked = temperature_array.copy()
    masked[:, solid_mask | (~study_area_3d)] = np.nan
    return {
        "temperature_fields_c": temperature_array,
        "temperature_fields_masked_c": masked,
        "fluid_mask": fluid_mask,
        "dt_seconds": float(dt),
        "substeps_per_frame": int(substeps),
        "frame_means_c": np.asarray(frame_means, dtype=np.float32),
        "solver_backend": "numpy",
    }


def shift_with_edge_torch(field: "torch.Tensor", axis: int, step: int) -> "torch.Tensor":
    shifted = torch.roll(field, shifts=step, dims=axis)
    if step > 0:
        index = [slice(None)] * field.ndim
        index[axis] = slice(0, step)
        edge_index = [slice(None)] * field.ndim
        edge_index[axis] = slice(0, 1)
        shifted[tuple(index)] = field[tuple(edge_index)]
    elif step < 0:
        index = [slice(None)] * field.ndim
        index[axis] = slice(step, None)
        edge_index = [slice(None)] * field.ndim
        edge_index[axis] = slice(field.shape[axis] - 1, field.shape[axis])
        shifted[tuple(index)] = field[tuple(edge_index)]
    return shifted


def impose_boundary_conditions_3d_torch(
    temperature_c: "torch.Tensor",
    solid_mask: "torch.Tensor",
    roof_mask: "torch.Tensor",
    study_area_3d: "torch.Tensor",
    roof_surface_temperature_excess_3d: "torch.Tensor",
    current_ambient_temp_c: float,
    current_inflow_temp_c: float,
) -> None:
    fluid_mask = (~solid_mask) & study_area_3d
    current_solid_temperature_3d = torch.full_like(temperature_c, float(current_ambient_temp_c))
    current_solid_temperature_3d[roof_mask] = (
        float(current_ambient_temp_c) + roof_surface_temperature_excess_3d[roof_mask]
    )
    temperature_c[solid_mask] = current_solid_temperature_3d[solid_mask]

    left_fluid = fluid_mask[:, :, 0]
    vertical_profile = torch.linspace(
        float(current_inflow_temp_c) + 0.1,
        float(current_inflow_temp_c) - 0.1,
        temperature_c.shape[0],
        dtype=temperature_c.dtype,
        device=temperature_c.device,
    )[:, None]
    left_boundary = temperature_c[:, :, 0]
    left_boundary[left_fluid] = vertical_profile.expand_as(left_boundary)[left_fluid]
    temperature_c[:, :, 0] = left_boundary

    temperature_c[:, :, -1] = torch.where(
        fluid_mask[:, :, -1],
        temperature_c[:, :, -2],
        temperature_c[:, :, -1],
    )
    temperature_c[:, 0, :] = torch.where(
        fluid_mask[:, 0, :],
        temperature_c[:, 1, :],
        temperature_c[:, 0, :],
    )
    temperature_c[:, -1, :] = torch.where(
        fluid_mask[:, -1, :],
        temperature_c[:, -2, :],
        temperature_c[:, -1, :],
    )
    temperature_c[-1, :, :] = torch.where(
        fluid_mask[-1, :, :],
        torch.as_tensor(float(current_ambient_temp_c), dtype=temperature_c.dtype, device=temperature_c.device),
        temperature_c[-1, :, :],
    )
    temperature_c[~study_area_3d] = float(current_ambient_temp_c)


def solve_temperature_fields_3d_torch(
    fields: dict[str, np.ndarray],
    boundary_fields: dict[str, np.ndarray],
    velocity_config: SouthKensingtonConfig,
    temp3d_config: Temperature3DScenarioConfig,
) -> dict[str, object]:
    if not TORCH_AVAILABLE:
        raise RuntimeError("temperature_solver_backend='cuda' requires PyTorch.")

    requested_device = str(temp3d_config.temperature_solver_device)
    if requested_device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("temperature_solver_device requests CUDA, but torch.cuda.is_available() is False.")
    device = torch.device(requested_device if requested_device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu"))

    u_frames_np = (temp3d_config.velocity_scale * fields["u"]).astype(np.float32)
    v_frames_np = (temp3d_config.velocity_scale * fields["v"]).astype(np.float32)
    w_frames_np = (temp3d_config.velocity_scale * fields["w"]).astype(np.float32)
    solid_mask_np = fields["solid_mask_3d"].astype(bool)
    study_area_3d_np = np.broadcast_to(fields["study_area_mask_2d"][None, :, :], solid_mask_np.shape).astype(bool)
    fluid_mask_np = (~solid_mask_np) & study_area_3d_np

    dx = float(velocity_config.model_resolution_m)
    dy = dx
    dz = float(velocity_config.height_scale_m)

    max_speed = float(np.max(np.sqrt(u_frames_np**2 + v_frames_np**2 + w_frames_np**2)))
    stable_dt = temp3d_config.max_courant * min(dx, dy, dz) / max(max_speed, 1e-6)
    diffusion_dt = 0.18 * min(dx, dy, dz) ** 2 / max(temp3d_config.diffusion_coeff_m2_s, 1e-6)
    dt = min(stable_dt, diffusion_dt, temp3d_config.frame_duration_s)
    substeps = max(1, int(math.ceil(temp3d_config.frame_duration_s / max(dt, 1e-6))))
    dt = temp3d_config.frame_duration_s / substeps

    u_frames = torch.as_tensor(u_frames_np, dtype=torch.float32, device=device)
    v_frames = torch.as_tensor(v_frames_np, dtype=torch.float32, device=device)
    w_frames = torch.as_tensor(w_frames_np, dtype=torch.float32, device=device)
    solid_mask = torch.as_tensor(solid_mask_np, dtype=torch.bool, device=device)
    roof_mask = torch.as_tensor(fields["roof_mask_3d"].astype(bool), dtype=torch.bool, device=device)
    study_area_3d = torch.as_tensor(study_area_3d_np, dtype=torch.bool, device=device)
    fluid_mask = (~solid_mask) & study_area_3d
    bottom_fluid = fluid_mask[0]
    bottom_exchange_coeff = torch.as_tensor(
        boundary_fields["surface_exchange_coeff_per_s"].astype(np.float32),
        dtype=torch.float32,
        device=device,
    )
    ground_surface_temperature_excess_c = torch.as_tensor(
        boundary_fields["ground_surface_temperature_excess_c"].astype(np.float32),
        dtype=torch.float32,
        device=device,
    )
    roof_surface_temperature_excess_3d = torch.as_tensor(
        boundary_fields["roof_surface_temperature_excess_3d"].astype(np.float32),
        dtype=torch.float32,
        device=device,
    )
    ambient_temp_series_c = boundary_fields["ambient_temp_series_c"].astype(np.float32)
    inflow_temp_series_c = boundary_fields["inflow_temp_series_c"].astype(np.float32)
    surface_forcing_layer_count = int(boundary_fields["surface_forcing_layer_count"][0])

    temperature_c = torch.full(
        solid_mask.shape,
        float(ambient_temp_series_c[0]),
        dtype=torch.float32,
        device=device,
    )
    impose_boundary_conditions_3d_torch(
        temperature_c,
        solid_mask,
        roof_mask,
        study_area_3d,
        roof_surface_temperature_excess_3d,
        current_ambient_temp_c=float(ambient_temp_series_c[0]),
        current_inflow_temp_c=float(inflow_temp_series_c[0]),
    )

    frames = [temperature_c.detach().cpu().numpy().copy()]
    frame_means = [float(temperature_c[fluid_mask].mean().detach().cpu())]
    diffusion_coeff = float(temp3d_config.diffusion_coeff_m2_s)

    with torch.no_grad():
        for frame_idx in range(u_frames.shape[0]):
            u = torch.where(fluid_mask, u_frames[frame_idx], torch.zeros((), dtype=torch.float32, device=device))
            v = torch.where(fluid_mask, v_frames[frame_idx], torch.zeros((), dtype=torch.float32, device=device))
            w = torch.where(fluid_mask, w_frames[frame_idx], torch.zeros((), dtype=torch.float32, device=device))
            current_ambient_temp_c = float(ambient_temp_series_c[min(frame_idx + 1, ambient_temp_series_c.shape[0] - 1)])
            current_inflow_temp_c = float(inflow_temp_series_c[min(frame_idx + 1, inflow_temp_series_c.shape[0] - 1)])
            current_ground_surface_temperature_c = (
                float(current_ambient_temp_c) + ground_surface_temperature_excess_c
            )

            for _ in range(substeps):
                if temp3d_config.on_substep is not None: temp3d_config.on_substep()
                left = shift_with_edge_torch(temperature_c, axis=2, step=1)
                right = shift_with_edge_torch(temperature_c, axis=2, step=-1)
                north = shift_with_edge_torch(temperature_c, axis=1, step=1)
                south = shift_with_edge_torch(temperature_c, axis=1, step=-1)
                below = shift_with_edge_torch(temperature_c, axis=0, step=1)
                above = shift_with_edge_torch(temperature_c, axis=0, step=-1)
                below[0, :, :] = temperature_c[0, :, :]

                dtdx_backward = (temperature_c - left) / dx
                dtdx_forward = (right - temperature_c) / dx
                dtdy_backward = (temperature_c - north) / dy
                dtdy_forward = (south - temperature_c) / dy
                dtdz_backward = (temperature_c - below) / dz
                dtdz_forward = (above - temperature_c) / dz

                adv_x = torch.where(u >= 0.0, u * dtdx_backward, u * dtdx_forward)
                adv_y = torch.where(v >= 0.0, v * dtdy_backward, v * dtdy_forward)
                adv_z = torch.where(w >= 0.0, w * dtdz_backward, w * dtdz_forward)
                laplacian = (
                    (left - 2.0 * temperature_c + right) / (dx**2)
                    + (north - 2.0 * temperature_c + south) / (dy**2)
                    + (below - 2.0 * temperature_c + above) / (dz**2)
                )

                surface_exchange_term = torch.zeros_like(temperature_c)
                for layer_idx in range(surface_forcing_layer_count):
                    layer_fluid = fluid_mask[layer_idx] & bottom_fluid
                    surface_exchange_term[layer_idx, layer_fluid] = (
                        bottom_exchange_coeff[layer_fluid]
                        * (
                            current_ground_surface_temperature_c[layer_fluid]
                            - temperature_c[layer_idx, layer_fluid]
                        )
                    )

                next_temperature = temperature_c + float(dt) * (
                    -(adv_x + adv_y + adv_z)
                    + diffusion_coeff * laplacian
                    + surface_exchange_term
                )
                temperature_c[fluid_mask] = next_temperature[fluid_mask]
                impose_boundary_conditions_3d_torch(
                    temperature_c,
                    solid_mask,
                    roof_mask,
                    study_area_3d,
                    roof_surface_temperature_excess_3d,
                    current_ambient_temp_c=current_ambient_temp_c,
                    current_inflow_temp_c=current_inflow_temp_c,
                )

            frames.append(temperature_c.detach().cpu().numpy().copy())
            frame_means.append(float(temperature_c[fluid_mask].mean().detach().cpu()))

    temperature_array = np.stack(frames, axis=0).astype(np.float32)
    masked = temperature_array.copy()
    masked[:, solid_mask_np | (~study_area_3d_np)] = np.nan
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return {
        "temperature_fields_c": temperature_array,
        "temperature_fields_masked_c": masked,
        "fluid_mask": fluid_mask_np,
        "dt_seconds": float(dt),
        "substeps_per_frame": int(substeps),
        "frame_means_c": np.asarray(frame_means, dtype=np.float32),
        "solver_backend": f"torch:{device}",
    }
