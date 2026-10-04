#version 120
// Pass 44 sky: fog-coloured horizon, time-of-day zenith, sun / moon disc, dusk glow, stars.
uniform vec4 sky_horizon;
uniform vec4 sky_zenith;
uniform vec3 sky_light_dir;
uniform vec4 sky_params;        // x night, y low-sun glow, z disc cosine, w disc strength
uniform vec4 sky_disc_colour;
varying vec3 v_dir;

float hash13(vec3 p) {
    p = fract(p * 0.1031);
    p += dot(p, p.yzx + 33.33);
    return fract((p.x + p.y) * p.z);
}

float hash12(vec2 p) {
    vec3 q = fract(vec3(p.xyx) * 0.1031);
    q += dot(q, q.yzx + 33.33);
    return fract((q.x + q.y) * q.z);
}

void main() {
    vec3 dir = normalize(v_dir);
    float h = dir.z;
    float night = sky_params.x;

    // horizon band stays exactly the fog colour so distant terrain has no seam
    float up = smoothstep(0.015, 1.0, h);
    vec3 col = mix(sky_horizon.rgb, sky_zenith.rgb, pow(up, 0.55));

    // warm glow toward a low sun (dawn / dusk), kept just above the horizon line
    vec2 flat_dir = normalize(dir.xy + vec2(1e-5));
    vec2 flat_sun = normalize(sky_light_dir.xy + vec2(1e-5));
    float toward = max(dot(flat_dir, flat_sun), 0.0);
    float band = smoothstep(0.0, 0.05, h) * (1.0 - smoothstep(0.05, 0.45, h));
    col += vec3(0.30, 0.14, 0.05) * sky_params.y * (1.0 - night) * pow(toward, 3.0) * band;

    // disc + soft halo
    float d = dot(dir, normalize(sky_light_dir));
    float disc = smoothstep(sky_params.z - 0.00012, sky_params.z, d);
    float halo = pow(max(d, 0.0), 180.0) * 0.22 + pow(max(d, 0.0), 12.0) * 0.06 * (1.0 - night);
    float above = smoothstep(-0.01, 0.02, h);
    col = mix(col, sky_disc_colour.rgb, disc * sky_params.w * above);
    col += sky_disc_colour.rgb * halo * above;

    // stars: one jittered point per cell, only in the dark part of the sky
    if (night > 0.001 && h > 0.0) {
        vec3 p = dir * 170.0;
        vec3 c = floor(p);
        float pick = hash13(c);
        if (pick > 0.985) {
            vec3 jitter = vec3(hash13(c + 1.7), hash13(c + 4.3), hash13(c + 9.1)) * 0.6 + 0.2;
            float r = length(p - c - jitter);
            float twinkle = 0.55 + 0.45 * hash13(c + 13.0);
            float star = (1.0 - smoothstep(0.05, 0.16, r)) * twinkle;
            col += vec3(0.86, 0.88, 1.0) * star * night * smoothstep(0.02, 0.25, h) * (1.0 - disc);
        }
    }

    // a touch of dither so the long gradients never band on 8-bit 4K panels
    col += (hash12(gl_FragCoord.xy) - 0.5) / 255.0;
    gl_FragColor = vec4(col, 1.0);
}
