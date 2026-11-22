# Healthy-route local visualization

The runnable `breathing_cvae` Method exports eight existing standard layers consumed directly by the shared scientific viewer: breathing, latent spread, temperature, pollution, irradiance, thermal proxy, experimental health score and trajectory. Start with `python model/tools/run_health_example.py --serve --open` from the checkout. No separate renderer or participant data is needed.

The private `wave_cvae` optimizer also exports standard trajectory, breathing and available environmental layers. Its detailed route artifact remains available for analysis.

The modules in this directory retain the earlier interactive private route interface, which expects a separate planning service. They are not the entry point for the now-runnable public-asset inference workflow and are not wired into the hosted website. Public-demo deployment is unchanged.
