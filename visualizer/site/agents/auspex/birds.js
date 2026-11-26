import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

// Auspex bird layer: the bird model, wing/head animation and feather shading of the Auspex flock viewer
// (birds/vis/viewer.html, feather-plumage), behind the same interface as agents/demo_rev02/birds.js
// (createBirdLayer -> {group, update(t), getState(i), setVisible, setMarkers, stats}) so the bird preview can switch renderer.
// Display only: positions, heading, speed, bank and state come from the recorded replay; flap, fold, peck and head
// stabilisation are derived from them in the vertex shader, exactly as in the Auspex viewer. Birdsong is not included.
//
// Optional per-bird data (the replay manifest), used when present, else neutral values:
//   manifest.identity = {energy_drain_rate, valence_disposition, arousal_excitability}, arrays of birds values in 0..1
//     -> which feather variant each bird wears (same lattice as bake_feathers.py: 5 levels per trait)
//   manifest.affect_file = 'bird_affect.u8': frame-major (frame * birds + bird) * 3 bytes
//     [energy 0..1, valence -1..1, arousal 0..1] each quantised to 0..255 -> energy lightness and mood sheen
//
// Changes from the Auspex viewer, all for three.js r185 / the CANOPY viewer:
//   - the per-instance colour attribute is named birdColor (r185 reserves instanceColor for InstancedMesh.instanceColor)
//   - the dFdx/dFdy extension flag is dropped (WebGL2 has derivatives built in)
//   - the replay is already in viewer axes (X, Y up, Z), so velocity is rebuilt from yaw/speed/vertical motion
//   - interpolation between recorded frames, and bank smoothing per rendered frame instead of per recorded frame
//   - the state rim and the sound-driven beak opening are off (birdsong is not part of this layer)

const STATE_NAMES = ['FORAGE', 'TRANSIT', 'MURMURATION', 'DESCENT', 'ROOST'];
const STATE_COLOURS = ['#4caf50', '#2196f3', '#ff9800', '#ff00ff', '#f44336'];
const BIRD_SIZE_M = 0.4;  // Auspex: 2x a starling's 0.2 m so birds stay visible
const BANK_SIGN = -1;     // Auspex applies -bank * 0.5 about the forward axis
const BANK_GAIN = 0.5;
const NEUTRAL = {energy: 0.8, valence: 0, arousal: 0}; // Auspex defaults when a run has no energy/affect

const VERTEX_SHADER = `      // per-vertex i.e. one value for each vertex of the bird mesh
      attribute float wingWeight; // 0=body, >0 left wing root to tip, <0 right wing
      attribute float headWeight; // 0=body/wing, 1=head
      attribute vec3 outlineNormal; // position-averaged normal (connected hull)
      attribute float visBeakData; // 0=always, 1=spread wing, 2=tucked wing, 3=legs, 4=lower beak, 5=upper beak, 6=tail

      // per-instance one value for each bird in the flock, shared by all vertices of that bird
      attribute vec3 birdColor; // bird color from getColor()
      attribute float flapOffset; // random phase offset, set once at init
      attribute vec4 stateData; // [birdState, bankAngle, speed, verticalVel]
      attribute vec4 extra; // [flareAngle, valence, arousal, beakOpen]
      attribute vec3 rimColor; // behavioral state color (updated per frame)

      uniform float uTime; // seconds
      uniform vec3 uNeckPivot; // neck joint position for nystagmus rotation
      uniform vec3 uBeakPivot; // beak hinge for open animation
      uniform float uWingSpan;
      uniform float uFlapAmp;

      varying vec3 vColor;
      flat varying vec3 vNormal;
      varying vec3 vRim; // state rim color
      varying vec3 vNormalView; // view-space normal for fresnel rim
      varying vec3 vViewPos; // view-space position for fresnel rim
      varying vec2 vAffect; // [valence, arousal] -> body color in fragment
      varying vec2 vUv; // mesh UV for atlas sampling
      varying vec3 vObjPos; // REST-pose object position: feathers are projected from this, so they stick to the mesh while it animates
      varying vec3 vObjN; // REST-pose normal: picks which axis the feathers are projected along
      varying float vRegion; // 0 body, 1 head, 2 tail, 3 spread wing, 5 tucked wing, 9 bare (legs + beak)
      varying vec2 vPatternOffset; // per-bird shift of the feather pattern, so birds sharing a variant tile still differ

      bool isPerspectiveMatrix( mat4 m ) { return m[2][3] == -1.0; }

      uniform float uShoulderY; // mean height of wing-root vertices = flap hinge height (set in JS)

      // FLAP HEIGHT PROFILE = the original baseFlap + tentOffset, as a function so the bend can sample its slope
      //   FLAP_UP / FLAP_DOWN = one gain for the whole wing, read from the wingtip's wingbeat (same at every span point),
      //   FLAP_UP at the top of the stroke and FLAP_DOWN at the bottom, blended smoothly through the cycle
      //   -> every pose is the original profile stretched vertically, so the tent never inverts and the wing never jumps
      // NOTE: no citation (OURS), gains tuned by eye in the plumage bench
      const float FLAP_UP = 1.1;
      const float FLAP_DOWN = 2.5;
      float flapHeight(float t, float phase, float kBase, float kTent) {
        // shoulder ramp: the wing root stays at the body and the wing turns about a hinge just outside it (0.2 to 0.5 units)
        // was 0.15 + 0.85 * smoothstep(0.10, 0.25, t), which bent the wing ~1 unit out and left the inner trailing edge
        // parked by the back like a frill; no ramp at all lets the wing roots cross over the back at the top of the stroke
        // NOTE: no citation (OURS), tuned by eye from rear renders at the top and bottom of the stroke
        float shoulderMask = smoothstep(0.03, 0.09, t);
        float baseFlap = sin(phase - t * 0.6) * t * 0.12 * kBase * shoulderMask;
        float tentStrength = (sin(phase) + 1.0) * 0.5 * 0.6 + 0.4;
        float tent = t < 0.55 ? t / 0.55 : 1.0 - (t - 0.55) / 0.45 * 0.5;
        float h = baseFlap + tent * tentStrength * 0.08 * kTent * shoulderMask;
        float g = mix(FLAP_DOWN, FLAP_UP, smoothstep(-1.0, 1.0, sin(phase - 0.6)));
        return g * h;
      }
      #include <logdepthbuf_pars_vertex>

      void main() {
        // unpack per-instance state
        float birdState = stateData.x; // 0=forage 1=transit 2=murm 3=descent 4=roost
        float bankAngle = stateData.y; // bank angle in radians
        float birdSpeed = stateData.z; // speed in m/s
        float vertVel   = stateData.w; // vertical velocity, negative=descending

        vec3 pos = position;

        vRim = rimColor;
        vAffect = extra.yz;
        vUv = uv;
        vObjPos = position;
        vObjN = normal;
        vRegion = (visBeakData > 2.5 && visBeakData < 5.5) ? 9.0   // legs, lower beak, upper beak
                : (visBeakData > 5.5) ? 2.0                       // tail
                : (abs(wingWeight) > 0.01) ? 3.0                  // spread wing
                : (visBeakData > 1.5 && visBeakData < 2.5) ? 5.0  // tucked wing
                : (headWeight > 0.5) ? 1.0 : 0.0;                 // head / body
        vPatternOffset = fract(vec2(0.618034, 0.414214) * flapOffset * 7.0); // flapOffset = random per bird (0..2pi)

        // VISIBILITY: decode packed visBeakData
        bool isLowerBeak = visBeakData > 3.5 && visBeakData < 4.5;
        float visGroup = visBeakData > 3.5 ? 0.0 : visBeakData; // 4 lower beak, 5 upper beak, 6 tail = always visible
        bool isGrounded = birdState < 0.5 || birdState > 3.5;

        // extra.x = descent flare angle, extra.w = sound-driven beak open (independent lanes)
        float flareAngle = max(extra.x, 0.0);
        float openFromSound = max(extra.w, 0.0);

        // WING ANIMATION
        if (abs(wingWeight) > 0.01) {

          // 1. FOLD = sweep wings backward along body during roost
          // rotates wing vertices around Y axis (up) at the shoulder
          // tip vertices (weight=1) fold more than root vertices (weight=0.25)
          float foldAmount = 0.0;
          if (birdState < 0.5) foldAmount = 1.2; // FORAGE = always folded (leg-powered hops, not wing-assisted)
          else if (birdState > 2.5) foldAmount = 1.2 * clamp(1.0 - birdSpeed / 3.0, 0.0, 1.0); // descent + roost: fold as speed drops
          
          if (foldAmount > 0.01) {
            // use actual X distance from body center for smooth fold
            // normalize by max wing span so tips fold most
            float foldAngle = foldAmount * abs(pos.x) / uWingSpan;
            float fSign = wingWeight > 0.0 ? -1.0 : 1.0;
            float cf = cos(fSign * foldAngle);
            float sf = sin(fSign * foldAngle);
            float foldX = pos.x * cf - pos.z * sf;
            float foldZ = pos.x * sf + pos.z * cf;
            pos.x = foldX;
            pos.z = foldZ;
          }

          // TUCK = rotate wing plane from horizontal to vertical (pressed against body)
          // applied after fold sweep, scaled by same foldAmount
          if (foldAmount > 0.01) {
            float tuckAngle = foldAmount * 1.3 * abs(pos.x) / uWingSpan; // tips tuck more
            float tSign = wingWeight > 0.0 ? 1.0 : -1.0;
            float ct = cos(tSign * tuckAngle);
            float st = sin(tSign * tuckAngle);
            // rotate around Z axis (forward) to make wing vertical
            float tuckX = pos.x * ct - pos.y * st;
            float tuckY = pos.x * st + pos.y * ct;
            pos.x = tuckX;
            pos.y = tuckY;
          }

          // 2. FLAP: variable tent = steep ^ shape on upstroke, flat-ish on downstroke
          float flapScale = 1.0 - foldAmount / 1.2;
          float freq = 10.0;
          float phase = uTime * freq + flapOffset;
          float t = abs(pos.x) / uWingSpan;

          // GLIDE = reduce overall flap amplitude smoothly during banked descent
          // scale the whole stroke, NOT parts of it (phase-dependent scaling can look jerky)
          float glideSuppress = 1.0;
          float glideAmount = smoothstep(0.15, 0.5, abs(bankAngle)) * smoothstep(-0.5, -2.0, vertVel);
          glideSuppress = mix(1.0, 0.3, glideAmount);

          // overall wing height oscillation (shoulder moves least, tip moves most)
          float flapPhase = phase - t * 0.6;
          // dead zone near shoulder: no displacement below 15% span, smoothly ramps from 0 to full between 15-30% span
          float shoulderMask = 0.15 + 0.85 * smoothstep(0.10, 0.25, t);
          // bigger flaps when slow (braking/landing), looks frantic without phase jumps (which was an issue when changing frequency)
          float brakingBoost = 1.0 + clamp(1.0 - birdSpeed / 6.0, 0.0, 1.0) * 0.8;
          float baseFlap = sin(flapPhase) * t * 0.12 * uFlapAmp * flapScale * glideSuppress * shoulderMask * brakingBoost;

          // tent shape that varies with phase:
          // upstroke (sin > 0): strong tent (steep ^)
          // downstroke (sin < 0): weak tent (nearly flat)
          // never negative = never inverts
          float tentStrength = (sin(phase) + 1.0) * 0.5 * 0.6 + 0.4; // 0.4 to 1.0, always some tent

          float peak = 0.55;
          float tent;
          if (t < peak) {
            tent = t / peak;
          } else {
            tent = 1.0 - (t - peak) / (1.0 - peak) * 0.5;
          }

          float tentOffset = tent * tentStrength * 0.08 * uFlapAmp * flapScale * glideSuppress * shoulderMask;

          // BEND instead of shear (was: pos.y += baseFlap + tentOffset;)
          // the same height profile (flapHeight above) sets the local ANGLE along the span and the wing is rebuilt from
          // those angles, so its length stays constant and the elbow rotates instead of stretching
          // NOTE: no citation (OURS), an inextensible-curve reconstruction of the existing tent profile
          {
            float kB = uFlapAmp * flapScale * glideSuppress * brakingBoost;
            float kT = uFlapAmp * flapScale * glideSuppress;
            float r = abs(pos.x);
            float sgn = pos.x < 0.0 ? -1.0 : 1.0;
            const int FLAP_STEPS = 12;
            float dr = r / float(FLAP_STEPS), X = 0.0, Y = 0.0, e = 0.004;
            for (int k = 0; k < FLAP_STEPS; k++) {
              float tm = (float(k) + 0.5) * dr / uWingSpan;
              float ang = atan((flapHeight(tm + e, phase, kB, kT) - flapHeight(tm - e, phase, kB, kT)) / (2.0 * e * uWingSpan));
              X += cos(ang) * dr;
              Y += sin(ang) * dr;
            }
            float th = atan((flapHeight(t + e, phase, kB, kT) - flapHeight(t - e, phase, kB, kT)) / (2.0 * e * uWingSpan));
            float yl = pos.y - uShoulderY; // wing thickness above/below the hinge turns with the wing
            pos.x = sgn * (X - sin(th) * yl);
            pos.y = uShoulderY + Y + cos(th) * yl;
          }
        }

        // NOTE: pitch-up handled in JS instance orientation, not here
        vec3 neckPivot = uNeckPivot;

        // HEAD NYSTAGMUS = head counter-rotates against bank (roll) and flight pitch
        if (headWeight > 0.01) {
          // roll compensation around Z (forward axis)
          float counterRoll = bankAngle * headWeight * 0.85;
          float ch = cos(counterRoll);
          float sh = sin(counterRoll);
          vec3 rel = pos - neckPivot;
          pos = neckPivot + vec3(rel.x * ch - rel.y * sh, rel.x * sh + rel.y * ch, rel.z);

          // pitch compensation around X (pitch axis)
          float pitch = asin(clamp(vertVel / max(birdSpeed, 1.0), -1.0, 1.0)); // flight path angle from vertical velocity
          // bird head is kept level with two separate corrections:
          // 1. flitch path pitch is countered at 0.6 (60%), a partial correction so head stays mostly level with horizon as bird climbs/dives
          // 2. descent flare angle is countered for head fully at 100%
          float counterPitch = -pitch * headWeight * 0.6 - flareAngle * headWeight;
          float cp = cos(counterPitch);
          float sp = sin(counterPitch);
          vec3 rel2 = pos - neckPivot;
          pos = neckPivot + vec3(rel2.x, rel2.y * cp - rel2.z * sp, rel2.y * sp + rel2.z * cp);

          // PECK ANIMATION = periodic head-dip around the neck pivot (X axis), half-wave so the head dips down then returns
          if (birdState < 0.5) {
            // birds stop walking to probe, so peck only fires when nearly still
            float probeGate = clamp(1.0 - birdSpeed * 30.0, 0.0, 1.0); // 1 when still, 0 when walking
            float probeFreq = 5.0; // ~5.0 Hz probe cycle
            float probePhase = uTime * probeFreq + flapOffset * 3.14159;
            float probeDip = max(sin(probePhase), 0.0); // half of sine wave
            probeDip *= probeDip; // sharpen so quick dip, longer with head up
            probeDip *= 0.7 * probeGate; // max dip ~0.7 rad = ~40 deg, only when stopped
            float cpk = cos(probeDip);
            float spk = -sin(probeDip);
            vec3 rel3 = pos - neckPivot;
            pos = neckPivot + vec3(rel3.x, rel3.y * cpk - rel3.z * spk, rel3.y * spk + rel3.z * cpk);
          }

          // BEAK OPENING = lower beak opens, driven by sound engine via extra.w
          if (isLowerBeak && openFromSound > 0.01) {
            float openAmt = openFromSound * 0.5; // scale to reasonable rotation (~0.25 rad max)
            float cg = cos(-openAmt);
            float sg = sin(-openAmt);
            vec3 relB = pos - uBeakPivot;
            pos = uBeakPivot + vec3(relB.x, relB.y * cg - relB.z * sg, relB.y * sg + relB.z * cg);
          }
        }

        // VISIBILITY: collapse hidden geometry to degenerate triangles
        if (visGroup > 0.5 && visGroup < 1.5 && isGrounded)  pos = vec3(0.0); // hide spread wings on ground
        if (visGroup > 1.5 && visGroup < 2.5 && !isGrounded) pos = vec3(0.0); // hide tucked wings in flight
        if (visGroup > 2.5 && !isGrounded)                   pos = vec3(0.0); // hide legs in flight

        #ifdef OUTLINE
        // inverted-hull outline = inflate along the normal
        // scaling grows linearly with camera distance, but capped at a scaling factor of 10.0
        // skip cel-shading for collapsed (hidden) vertices
        bool collapsed = (visGroup > 0.5 && visGroup < 1.5 && isGrounded)
                      || (visGroup > 1.5 && visGroup < 2.5 && !isGrounded)
                      || (visGroup > 2.5 && !isGrounded);
        if (!collapsed) {
          float camDist = distance(cameraPosition, (instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz);
          pos += normalize(outlineNormal) * uOutlinePx * min(1.0 + camDist * 0.1, 10.0);
        }
        #endif

        // apply instance transform
        vec4 worldPos = instanceMatrix * vec4(pos, 1.0);
        vec4 mvPos = modelViewMatrix * vec4(worldPos.xyz, 1.0);
        gl_Position = projectionMatrix * mvPos;
        #include <logdepthbuf_vertex>

        vColor = birdColor;
        vNormal = mat3(instanceMatrix) * normal;
        vViewPos = mvPos.xyz;
        vNormalView = mat3(modelViewMatrix) * (mat3(instanceMatrix) * normal);
      }`;
const FRAGMENT_SHADER = `      varying vec3 vColor;
      flat varying vec3 vNormal;
      varying vec3 vRim;
      varying vec3 vNormalView;
      varying vec3 vViewPos;
      varying vec2 vAffect;
      varying vec2 vUv;
      varying vec3 vObjPos;
      varying vec3 vObjN;
      varying float vRegion;
      varying vec2 vPatternOffset;
      uniform sampler2D uMarkAtlas;

      #include <logdepthbuf_pars_fragment>
      uniform vec2 uAtlasInner; // inner tile size in atlas UV units
      uniform vec2 uAtlasPad; // border/gutter width in atlas UV units
      uniform float uAtlasRepeat; // atlas tiles per local unit

      // affect -> Oklab ranges (NOTE: must match config.py VALENCE_A_RANGE / AROUSAL_B_RANGE)
      // valence -1 (bad) -> a=+0.13 (red); +1 (good) -> a=-0.05 (green)
      // arousal  0 (calm) -> b=-0.09 (blue); 1 -> b=+0.09 (yellow)
      const vec2 VAL_A = vec2(0.13, -0.05); // (at valence -1, at valence +1)
      const vec2 ARO_B = vec2(-0.09, 0.09); // (at arousal 0, at arousal 1)
      const vec2 AFFECT_L = vec2(0.45, 0.73); // body lightness from energy (low to high)

      // Oklab -> linear sRGB (see https://bottosson.github.io/posts/oklab/)
      vec3 oklabToLinear(float L, float a, float b) {
        float l_ = L + 0.3963377774*a + 0.2158037573*b;
        float m_ = L - 0.1055613458*a - 0.0638541728*b;
        float s_ = L - 0.0894841775*a - 1.2914855480*b;
        float l = l_*l_*l_, m = m_*m_*m_, s = s_*s_*s_;
        return vec3(
          4.0767416621*l - 3.3077115913*m + 0.2309699292*s,
         -1.2684380046*l + 2.6097574011*m - 0.3413193965*s,
         -0.0041960863*l - 0.7034186147*m + 1.7076147010*s
        );
      }
      vec3 linearToSrgb(vec3 c) {
        vec3 lo = 12.92 * c;
        vec3 hi = 1.055 * pow(max(c, 0.0), vec3(1.0/2.4)) - 0.055;
        return mix(lo, hi, step(0.0031308, c));
      }

      float hash13(vec3 p) {
        p = fract(p * 0.1031);
        p += dot(p, p.yzx + 33.33);
        return fract((p.x + p.y) * p.z);
      }

      // sample this bird's marking texture
      // with the atlas: vColor.gb stores this bird's tile origin
      // fract() repeats the pattern inside that tile without bleeding into neighbouring tiles
      // without the atlas: return white (i.e. no markings)
      float markTexel(vec2 p) {
      #ifdef NO_MARKS
        return 1.0; // white = no mark (quick export / no atlas embedded)
      #else
        vec2 uv = vColor.gb + uAtlasPad + fract(p) * uAtlasInner;
        return texture2D(uMarkAtlas, uv).r;
      #endif
      }

      #ifdef FEATHER_MARKS
      // FEATHER MARKS (bake_feathers.py): atlas texel = (tone, t, |s|, shadow) of the feather visible at that point
      //   tone   = per-feather tone (coherence trait)
      //   t      = 0 at the feather's base .. 1 at its tip
      //   |s|    = 0 on the shaft .. 1 at the vane margin
      //   shadow = 0..1 occlusion just past the edge of an overlying feather
      // colour = species base (fixed) + mood sheen (live valence/arousal) + energy lightness (live, vColor.r as before)
      // NOTE: every constant below was tuned by eye in the plumage bench, no citation (OURS)
      const float FEATHER_REPEAT = 8.0;   // atlas tiles per metre of bird (object space, after the 0.4 m rescale)
      const float WING_SWEEP = 0.349066;  // 20 deg, wing feathers angle outward
      const vec2 SPECIES_AB = vec2(-0.011971, -0.032889); // species colour, Oklab (a, b): slate = hue 250 deg, chroma 0.035
      const float TONE_AMP = 0.24;        // lightness swing between the lightest and darkest feather tones
      const float SHEEN_GAIN = 2.5;       // mood colour vividness in the sheen (x the body-colour Oklab ranges)
      const float SHEEN_FLOOR = 0.6;      // sheen seen head-on (rises to 1 at glancing angles)
      const float SHEEN_TIP = 0.4;        // 0 = sheen over the whole feather, 1 = only on its exposed tip
      const float LIGHT_GAIN = 0.8;       // overall brightness of the feather shading (1.0 clipped light feathers to white)
      const float SHEEN_SWING = 0.436332; // 25 deg hue swing either side of the mood hue (average = mood hue)
      const float SHEEN_BANDS = 1.5;      // hue bands along each feather
      const float RELIEF = 0.4;           // bump strength of the feather relief
      const float DIFFUSE_W = 0.5;        // diffuse weight in feather mode (voronoi mode uses 0.3)
      const vec3 BARE_RGB = vec3(0.46, 0.42, 0.37); // legs + beak, muted horn grey (sRGB)

      vec2 rot2(vec2 p, float ang) { float c = cos(ang), s = sin(ang); return vec2(c * p.x - s * p.y, s * p.x + c * p.y); }

      vec4 featherTexel(vec2 p) {
        vec2 uv = vColor.gb + uAtlasPad + fract(p + vPatternOffset) * uAtlasInner;
        return texture2D(uMarkAtlas, uv);
      }

      // colour of one projection (before lighting) in .rgb, relief height in .a
      vec4 featherShade(vec2 p, float L0, vec2 mood, float fres) {
        vec4 F = featherTexel(p);
        float tone = F.r, t = F.g, s = F.b, sh = F.a;
        // relief: vanes domed across, dipping under the edge of the feather above
        float h = 0.55 * (1.0 - sh) + 0.30 * (1.0 - s * s);
        // shaft and barbs from (t, |s|) alone: feathers are 3.4 R long and 0.8 R wide, barbs R/3.5 apart at 40 deg (bake_feathers constants)
        float rach = exp(-pow(16.0 * s, 2.0)) * step(t, 0.92);
        float barb = 0.5 + 0.5 * cos(6.2831853 * 3.5 * (3.4 * t - 0.8 * 1.1918 * s));
        float vane = clamp(1.0 - s, 0.0, 1.0);
        float d = clamp((tone - 0.30) / 0.25, -1.0, 1.0); // -1 darkest .. +1 lightest feather
        float L = L0 + TONE_AMP * d + 0.03 * rach - 0.02 * (barb - 0.5) * vane;
        vec2 ab = SPECIES_AB * (1.0 - 0.25 * d); // darker feathers slightly richer
        // MOOD SHEEN: colour = live mood, strongest on exposed tips and at glancing angles
        float view = SHEEN_FLOOR + (1.0 - SHEEN_FLOOR) * pow(fres, 1.5);
        float S = view * mix(1.0, smoothstep(0.45, 0.95, t), SHEEN_TIP) * (1.0 - 0.7 * sh);
        float band = sin(6.2831853 * (SHEEN_BANDS * t + 0.8 * fres));
        ab = mix(ab, rot2(mood, SHEEN_SWING * band), clamp(S, 0.0, 1.0));
        L += 0.03 * S;
        L *= 1.0 - 0.30 * sh;
        return vec4(linearToSrgb(oklabToLinear(L, ab.x, ab.y)), h);
      }

      // bump-mapped normal from a height without UV tangents (surface-gradient form, as in three.js perturbNormalArb)
      vec3 featherBump(vec3 pos, vec3 n, float h) {
        vec2 dH = vec2(dFdx(h), dFdy(h)) * RELIEF * 0.012;
        vec3 sx = dFdx(pos), sy = dFdy(pos);
        vec3 r1 = cross(sy, n), r2 = cross(n, sx);
        float det = dot(sx, r1);
        vec3 grad = sign(det) * (dH.x * r1 + dH.y * r2);
        return normalize(abs(det) * n - grad);
      }

      vec3 featherColor(float L0, float valence, float arousal, vec3 lightDirWorld) {
        vec3 N = normalize(vNormalView);
        if (!gl_FrontFacing) N = -N;
        float fres = 1.0 - abs(dot(N, normalize(-vViewPos)));
        vec3 Lv = normalize(mat3(viewMatrix) * lightDirWorld);
        if (vRegion > 8.5) return BARE_RGB * (0.7 + DIFFUSE_W * abs(dot(N, Lv))); // legs + beak: no feathers
        vec2 mood = vec2(mix(VAL_A.x, VAL_A.y, (valence + 1.0) * 0.5), mix(ARO_B.x, ARO_B.y, arousal)) * SHEEN_GAIN;
        // project along the axis the (rest-pose) surface faces; feathers point along +v = tailward (+z) or down
        vec3 n0 = normalize(vObjN);
        vec3 w = pow(abs(n0), vec3(6.0)); w /= (w.x + w.y + w.z);
        if (vRegion > 1.5 && vRegion < 3.5) { w = vec3(0.0, pow(abs(n0.y), 4.0), pow(abs(n0.z), 4.0)); w /= (w.y + w.z + 1e-6); } // tail + spread wings lie flat in xz: no span-wise smear
        if (vRegion > 4.5 && vRegion < 5.5) { w = vec3(pow(abs(n0.x), 2.0), pow(abs(n0.y), 4.0), 0.0); w /= (w.x + w.y + 1e-6); } // tucked wings stand vertical
        float yaw = (vRegion > 2.5 && vRegion < 5.5) ? WING_SWEEP * sign(vObjPos.x) : 0.0;
        vec4 c = featherShade(vObjPos.yz * FEATHER_REPEAT, L0, mood, fres) * w.x
               + featherShade(rot2(vObjPos.xz, yaw) * FEATHER_REPEAT, L0, mood, fres) * w.y
               + featherShade(vec2(vObjPos.x, -vObjPos.y) * FEATHER_REPEAT, L0, mood, fres) * w.z;
        vec3 Nb = featherBump(vViewPos, N, c.a);
        return c.rgb * (0.7 + DIFFUSE_W * abs(dot(Nb, Lv))) * LIGHT_GAIN;
      }
      #endif

      void main() {
        #include <logdepthbuf_fragment>

        // BODY COLOR FROM AFFECT (Oklab)
        float valence = vAffect.x;
        float arousal = vAffect.y;
        float a = mix(VAL_A.x, VAL_A.y, (valence + 1.0) * 0.5);
        float bb = mix(ARO_B.x, ARO_B.y, arousal);
        float L = vColor.r;
        vec3 bodyLin = oklabToLinear(L, a, bb);

        vec3 lightDir = normalize(vec3(0.5, 0.8, -0.3));
        float diffuse = abs(dot(normalize(vNormal), lightDir));
        float ambient = 0.7;
        vec3 color = linearToSrgb(bodyLin) * (ambient + diffuse * 0.3);

      #ifdef FEATHER_MARKS
        // FEATHER MODE: species colour + mood sheen + energy lightness, see featherColor()
        color = featherColor(L, valence, arousal, lightDir);
      #else
        // UV sampling: one fetch of this bird's tile via the mesh unwrap
        // markTexel() wraps with fract(), so UVs outside 0 to 1 tile seamlessly (the pattern is toroidal)
        float texel = markTexel(vUv * uAtlasRepeat);
        float markAmt = 1.0 - texel;

        // darken in Oklab L (perceptual) instead of multiplying sRGB
        float LdarkAmt = 0.30; // how far down L a full mark pulls (0=none, 1=black)
        float Lmarked = L * (1.0 - LdarkAmt * markAmt);
        vec3 markedLin = oklabToLinear(Lmarked, a, bb);
        vec3 marked = linearToSrgb(markedLin) * (ambient + diffuse * 0.3);
        color = marked;
      #endif

        // BEHAVIORAL STATE RIM
        float rim = 1.0 - max(0.0, dot(normalize(vNormalView), normalize(-vViewPos)));
        rim = pow(rim, 2.5);
        float rimActive = step(0.01, vRim.r + vRim.g + vRim.b);
        color = mix(color, vRim, rim * 0.7 * rimActive);

        gl_FragColor = vec4(color, 1.0);
      }`;

async function loadAtlas(baseURL) {
  const meta = await (await fetch(new URL('feather_atlas.json', baseURL))).json();
  const blob = await (await fetch(new URL('feather_atlas.png', baseURL))).blob();
  // alpha is DATA (shadow), not opacity: decode without premultiplying or colour conversion
  const bitmap = await createImageBitmap(blob, {premultiplyAlpha: 'none', colorSpaceConversion: 'none'});
  const tex = new THREE.Texture(bitmap);
  tex.flipY = false; tex.generateMipmaps = false;
  tex.minFilter = tex.magFilter = THREE.LinearFilter;
  tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
  tex.premultiplyAlpha = false; tex.colorSpace = THREE.NoColorSpace; tex.needsUpdate = true;
  return {meta, tex};
}

// Auspex loadBirdModel: scale, face forward, decode painted regions into wing/head/visibility weights, pivots, outline normals
function prepareBirdGeometry(geo) {
  geo.computeBoundingBox();
  let b = geo.boundingBox;
  const scale = BIRD_SIZE_M / Math.max(b.max.x - b.min.x, b.max.y - b.min.y, b.max.z - b.min.z);
  geo.scale(scale, scale, scale);
  geo.computeBoundingBox(); b = geo.boundingBox;
  const wingSpan = (b.max.x - b.min.x) / 2;
  geo.rotateY(Math.PI);
  const n = geo.attributes.position.count, P = geo.attributes.position;
  const wingW = new Float32Array(n), headW = new Float32Array(n), vis = new Float32Array(n);
  const vc = ['color', '_color', 'color_0', 'COLOR_0'].map(k => geo.attributes[k]).find(Boolean);
  if (!vc) throw new Error('bird.glb has no painted vertex colours');
  const arr = vc.array, stride = vc.itemSize;
  let maxVal = 0; for (let i = 0; i < arr.length; i++) if (arr[i] > maxVal) maxVal = arr[i];
  const cs = (arr instanceof Uint16Array) ? 1 / 65535 : (arr instanceof Uint8Array) ? 1 / 255 : (maxVal > 1.5 ? 1 / maxVal : 1);
  for (let i = 0; i < n; i++) {
    const r = arr[i * stride] * cs, g = arr[i * stride + 1] * cs, bl = arr[i * stride + 2] * cs;
    const rHi = r > .6, rMid = r > .12 && r <= .6, rLo = r <= .12, gHi = g > .6, gMid = g > .12 && g <= .6, gLo = g <= .12;
    const bHi = bl > .6, bMid = bl > .12 && bl <= .6, bLo = bl <= .12;
    const isTail = rMid && bMid && gLo, isLeft = (rHi && gLo && bLo) || (rMid && gLo && bLo && !isTail);
    const isRight = (gHi && rLo && bLo) || (gMid && rLo && bLo), isHead = bHi && rLo && gLo, isBeak = bMid && rLo && gLo && !isTail;
    const isTucked = rHi && gMid && bLo, isLeg = rHi && gHi && bLo, isLowerBeak = rLo && gMid && bMid;
    wingW[i] = isLeft ? 1 : isRight ? -1 : 0;
    headW[i] = (isHead || isBeak || isLowerBeak) ? 1 : 0;
    vis[i] = (isLeft || isRight) ? 1 : isTucked ? 2 : isLeg ? 3 : isLowerBeak ? 4 : isBeak ? 5 : isTail ? 6 : 0;
  }
  const neck = new THREE.Vector3(); let nh = 0;
  for (let i = 0; i < n; i++) if (headW[i] > .01) { neck.x += P.getX(i); neck.y += P.getY(i); neck.z += P.getZ(i); nh++; }
  if (nh) neck.divideScalar(nh);
  let shoulderY = 0, ns = 0;
  for (let i = 0; i < n; i++) if (Math.abs(wingW[i]) > .01 && Math.abs(P.getX(i)) < .2 * wingSpan) { shoulderY += P.getY(i); ns++; }
  if (ns) shoulderY /= ns;
  const beak = new THREE.Vector3(); let nb = 0, beakTop = -Infinity;
  for (let i = 0; i < n; i++) if (vis[i] > 3.5 && vis[i] < 4.5) { beak.x += P.getX(i); beak.z += P.getZ(i); beakTop = Math.max(beakTop, P.getY(i)); nb++; }
  if (nb) { beak.x /= nb; beak.z /= nb; beak.y = beakTop; } else beak.copy(neck);
  const N = geo.attributes.normal, smooth = new Float32Array(n * 3), acc = new Map();
  for (let i = 0; i < n; i++) {
    const k = P.getX(i).toFixed(4) + ',' + P.getY(i).toFixed(4) + ',' + P.getZ(i).toFixed(4);
    let a = acc.get(k); if (!a) acc.set(k, a = [0, 0, 0, []]);
    a[0] += N.getX(i); a[1] += N.getY(i); a[2] += N.getZ(i); a[3].push(i);
  }
  for (const a of acc.values()) { const l = Math.hypot(a[0], a[1], a[2]) || 1; for (const i of a[3]) { smooth[i * 3] = a[0] / l; smooth[i * 3 + 1] = a[1] / l; smooth[i * 3 + 2] = a[2] / l; } }
  geo.setAttribute('outlineNormal', new THREE.BufferAttribute(smooth, 3));
  for (const k of ['color', '_color', 'color_0', 'COLOR_0']) if (geo.attributes[k]) geo.deleteAttribute(k);
  geo.setAttribute('wingWeight', new THREE.BufferAttribute(wingW, 1));
  geo.setAttribute('headWeight', new THREE.BufferAttribute(headW, 1));
  geo.setAttribute('visBeakData', new THREE.BufferAttribute(vis, 1));
  return {wingSpan, shoulderY, neck, beak};
}

export async function createBirdLayer({scene, manifest, buffer, states, affect = null, assetsURL = new URL('./', import.meta.url).href}) {
  const N = manifest.birds, F = manifest.frames, dt = manifest.frame_dt_s, t0 = manifest.first_frame_t_s;
  const R = manifest.record.length, hasBank = manifest.record.includes('bank_rad');
  const group = new THREE.Group(); group.name = 'Bird layer (Auspex)';
  const [gltf, atlas] = await Promise.all([new GLTFLoader().loadAsync(new URL('bird.glb', assetsURL).href), loadAtlas(assetsURL)]);
  let geo = null; gltf.scene.traverse(o => { if (o.isMesh && !geo) geo = o.geometry; });
  if (!geo) throw new Error('No mesh found in bird.glb');
  const rig = prepareBirdGeometry(geo);
  const {meta, tex} = atlas, stored = meta.tile + 2 * meta.pad;

  // feather variant per bird: identity traits -> nearest lattice level per trait (bake_feathers._variant_of)
  const id = manifest.identity ?? null, L = meta.levels;
  const tileOrigin = new Float32Array(N * 2);
  for (let i = 0; i < N; i++) {
    const lv = meta.trait_order.map(k => Math.round(Math.min(1, Math.max(0, id?.[k]?.[i] ?? 0.5)) * (L - 1)));
    const tile = (lv[0] * L + lv[1]) * L + lv[2];
    tileOrigin[i * 2] = (tile % meta.cols) * stored / meta.w;
    tileOrigin[i * 2 + 1] = Math.floor(tile / meta.cols) * stored / meta.h;
  }

  const uniforms = {
    uTime: {value: 0}, uAtlasRepeat: {value: 3}, uMarkAtlas: {value: tex},
    uAtlasInner: {value: new THREE.Vector2(meta.tile / meta.w, meta.tile / meta.h)},
    uAtlasPad: {value: new THREE.Vector2(meta.pad / meta.w, meta.pad / meta.h)},
    uNeckPivot: {value: rig.neck}, uBeakPivot: {value: rig.beak}, uWingSpan: {value: rig.wingSpan},
    uShoulderY: {value: rig.shoulderY}, uFlapAmp: {value: 0.6}, uOutlinePx: {value: 0.004},
  };
  const material = new THREE.ShaderMaterial({vertexShader: VERTEX_SHADER, fragmentShader: '#define FEATHER_MARKS\n' + FRAGMENT_SHADER, side: THREE.DoubleSide, uniforms});
  const birds = new THREE.InstancedMesh(geo, material, N);
  birds.name = 'Birds (Auspex)'; birds.frustumCulled = false; birds.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  const attr = (name, size, usage = true) => { const a = new THREE.InstancedBufferAttribute(new Float32Array(N * size), size); if (usage) a.setUsage(THREE.DynamicDrawUsage); geo.setAttribute(name, a); return a; };
  const colorA = attr('birdColor', 3), stateA = attr('stateData', 4), extraA = attr('extra', 4), rimA = attr('rimColor', 3, false);
  const flapA = attr('flapOffset', 1, false);
  for (let i = 0; i < N; i++) flapA.array[i] = (i * 2.399963) % (2 * Math.PI); // golden-angle spread: stable across reloads (Auspex: random)
  const outline = new THREE.InstancedMesh(geo, new THREE.ShaderMaterial({
    vertexShader: '#define OUTLINE\nuniform float uOutlinePx;\n' + VERTEX_SHADER,
    fragmentShader: '#include <logdepthbuf_pars_fragment>\nvoid main() {\n#include <logdepthbuf_fragment>\ngl_FragColor = vec4(0.02, 0.02, 0.05, 1.0);\n}',
    side: THREE.BackSide, uniforms,
  }), N);
  outline.name = 'Birds outline (Auspex)'; outline.frustumCulled = false; outline.instanceMatrix = birds.instanceMatrix;
  group.add(birds, outline);

  const markers = new THREE.Points(new THREE.BufferGeometry(), new THREE.PointsMaterial({size: 2.5, sizeAttenuation: false, vertexColors: true, depthTest: false, depthWrite: false, transparent: true, opacity: .9}));
  markers.geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
  markers.geometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
  markers.frustumCulled = false; markers.renderOrder = 19; group.add(markers);
  scene.add(group);

  const obj = new THREE.Object3D(), fwd = new THREE.Vector3(), back = new THREE.Vector3(), right = new THREE.Vector3(), up = new THREE.Vector3();
  const WORLD_UP = new THREE.Vector3(0, 1, 0), basis = new THREE.Matrix4(), qBank = new THREE.Quaternion(), qFlare = new THREE.Quaternion(), qTmp = new THREE.Quaternion();
  const one = new THREE.Vector3(1, 1, 1), zero = new THREE.Vector3(0, 0, 0), colour = new THREE.Color();
  const smoothedBank = new Float32Array(N), lastYaw = new Float32Array(N), current = new Array(N);
  let markersWanted = true, lastWall = null;
  const record = (f, i) => { const k = (f * N + i) * R; return buffer.subarray(k, k + R); };
  const angleLerp = (a, b, s) => a + Math.atan2(Math.sin(b - a), Math.cos(b - a)) * s;
  const affectAt = (f, i, k) => affect ? affect[(f * N + i) * 3 + k] / 255 : null;

  function update(t) {
    let f = (t - t0) / dt; if (!(f >= 0)) f = 0; if (f > F - 1) f = F - 1;
    const f0 = Math.floor(f), f1 = Math.min(F - 1, f0 + 1), s = f - f0;
    const inRange = t >= t0 - dt && t <= manifest.last_frame_t_s + dt;
    const wall = performance.now() / 1000, dWall = lastWall === null ? 1 : Math.min(.25, Math.max(0, wall - lastWall)); lastWall = wall;
    const bankStep = 1 - Math.pow(0.8, dWall * 30); // Auspex: 0.2 per recorded frame at ~30 fps playback
    uniforms.uTime.value = wall;
    const stateCounts = [0, 0, 0, 0, 0], mp = markers.geometry.attributes.position, mc = markers.geometry.attributes.color;
    for (let i = 0; i < N; i++) {
      const a = record(f0, i), b = record(f1, i), st = states[f0 * N + i];
      stateCounts[st] = (stateCounts[st] ?? 0) + 1;
      const x = a[0] + (b[0] - a[0]) * s, y = a[1] + (b[1] - a[1]) * s, z = a[2] + (b[2] - a[2]) * s;
      const speed = a[4] + (b[4] - a[4]) * s, bank = hasBank ? a[5] + (b[5] - a[5]) * s : 0;
      const vUp = f1 > f0 ? (b[1] - a[1]) / dt : 0;
      const vh = Math.sqrt(Math.max(speed * speed - vUp * vUp, 0));
      const orientThresh = st === 0 ? 0.05 : 0.5;
      let yaw = angleLerp(a[3], b[3], s);
      if (speed > orientThresh) lastYaw[i] = yaw; else yaw = lastYaw[i];
      const groundLift = (st === 0 || st === 4) ? 0.06 : 0;
      obj.position.set(x, y + groundLift, z);
      const flare = st === 3 ? Math.min(1, Math.max(0, (10 - speed) / 7)) : 0;
      if (speed > orientThresh) {
        fwd.set(Math.sin(yaw) * vh, speed < 3 ? vUp * 0.2 : vUp, Math.cos(yaw) * vh).normalize();
        right.crossVectors(fwd, WORLD_UP); if (right.lengthSq() < .001) right.set(1, 0, 0); right.normalize();
        up.crossVectors(right, fwd);
        basis.makeBasis(right, up, back.copy(fwd).negate());
        obj.quaternion.setFromRotationMatrix(basis);
        const targetBank = (st >= 1 && st < 4) ? BANK_SIGN * bank * BANK_GAIN : 0;
        smoothedBank[i] += (targetBank - smoothedBank[i]) * bankStep;
        if (Math.abs(smoothedBank[i]) > .001) { qBank.setFromAxisAngle(fwd, smoothedBank[i]); obj.quaternion.premultiply(qBank); }
        if (flare > .01) { qFlare.setFromAxisAngle(right, 0.6); qTmp.copy(obj.quaternion).premultiply(qFlare); obj.quaternion.slerp(qTmp, flare); }
      } else {
        fwd.set(Math.sin(yaw), 0, Math.cos(yaw));
        right.crossVectors(fwd, WORLD_UP).normalize(); up.crossVectors(right, fwd);
        basis.makeBasis(right, up, back.copy(fwd).negate());
        obj.quaternion.setFromRotationMatrix(basis);
        smoothedBank[i] += (0 - smoothedBank[i]) * bankStep;
      }
      obj.matrix.compose(obj.position, obj.quaternion, inRange ? one : zero);
      birds.setMatrixAt(i, obj.matrix);
      const e = affectAt(f0, i, 0) ?? NEUTRAL.energy;
      colorA.setXYZ(i, 0.45 + e * (0.73 - 0.45), tileOrigin[i * 2], tileOrigin[i * 2 + 1]);
      const va = affect ? affectAt(f0, i, 1) * 2 - 1 : NEUTRAL.valence, ar = affectAt(f0, i, 2) ?? NEUTRAL.arousal;
      extraA.setXYZW(i, 0.6 * flare, va, ar, 0);
      stateA.setXYZW(i, st, smoothedBank[i], speed, vUp);
      current[i] = {idIndex: i, x, y, z, headingRadians: yaw, speed, bank, state: st, stateName: STATE_NAMES[st] ?? String(st), airborne: st !== 4 && st !== 0, visible: inRange};
      colour.set(STATE_COLOURS[st] ?? '#ffffff'); mp.setXYZ(i, x, y + .5, z); mc.setXYZ(i, colour.r, colour.g, colour.b);
    }
    birds.instanceMatrix.needsUpdate = true;
    colorA.needsUpdate = stateA.needsUpdate = extraA.needsUpdate = true;
    mp.needsUpdate = mc.needsUpdate = true;
    markers.visible = markersWanted && group.visible && inRange;
    return {present: inRange ? N : 0, stateCounts, frame: f0};
  }
  return {
    group, mesh: birds, update,
    getState: i => current[i] ?? null,
    setVisible: v => { group.visible = v; markers.visible = v && markersWanted; },
    setMarkers: v => { markersWanted = v; markers.visible = v && group.visible; },
    stats: {birds: N, frames: F, frame_dt_s: dt, first_t_s: t0, last_t_s: manifest.last_frame_t_s,
            model: 'Auspex bird.glb with feather shading (display only)', model_error: null, placeholder_model: false,
            identity: Boolean(id), affect: Boolean(affect)},
    STATE_NAMES, STATE_COLOURS,
  };
}
