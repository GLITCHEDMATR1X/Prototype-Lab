#version 150
in vec2 v_uv;
out vec4 p3d_FragColor;
uniform float overlay_time;
uniform float overlay_strength;
uniform float scanline_strength;
uniform float distortion_strength;
uniform float vignette_strength;
uniform float tear_strength;
uniform sampler2D tint_tex;
uniform vec4 tint_uv_transform;
uniform float lens_alpha;
uniform vec4 palette_tint;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

void main() {
    vec2 uv = clamp(v_uv, 0.0, 1.0);
    vec2 px = floor(gl_FragCoord.xy);

    // True television-style snow: the sample location never moves.  A quantized frame
    // seed changes the random value at each screen pixel, so the pattern flickers in
    // place rather than scrolling, panning, swimming, or drifting.
    float frame_seed = floor(overlay_time * 30.0);
    float fine = hash12(px + vec2(frame_seed * 37.0, frame_seed * 17.0));
    float fine2 = hash12(px.yx + vec2(frame_seed * 11.0 + 71.0, frame_seed * 29.0 + 19.0));
    vec2 coarse_px = floor(px / 3.0);
    float coarse = hash12(coarse_px + vec2(frame_seed * 23.0 + 13.0, frame_seed * 7.0 + 97.0));
    float snow = clamp(fine * 0.52 + fine2 * 0.30 + coarse * 0.18, 0.0, 1.0);

    // Scanlines are spatially fixed.  Only their brightness flickers slightly.
    float scan_phase = mod(px.y, 4.0);
    float scan_pattern = (scan_phase < 1.0) ? 1.0 : ((scan_phase < 2.0) ? 0.55 : 0.10);
    float scan_flicker = 0.90 + hash12(vec2(frame_seed, 412.0)) * 0.10;
    float scan_dark = (1.0 - scan_pattern) * scanline_strength * scan_flicker;

    // Separate interference events: these do not travel.  They pop into different rows
    // at a slower cadence, then vanish, which reads as sync damage rather than moving snow.
    float interference_seed = floor(overlay_time * 5.0);
    float row = floor(px.y / 18.0);
    float band_rand = hash12(vec2(row, interference_seed * 3.0 + 5.0));
    float band_mask = step(0.90, band_rand);
    float band_noise = hash12(vec2(floor(px.x / 12.0), row + interference_seed * 41.0));
    float bands = band_mask * band_noise * distortion_strength;

    float tear_seed = floor(overlay_time * 3.0);
    float tear_row_rand = hash12(vec2(row + 83.0, tear_seed * 19.0));
    float tear_mask = step(0.965, tear_row_rand);
    float tear_shape = smoothstep(0.16, 0.72, hash12(vec2(floor(px.x / 26.0), row * 7.0 + tear_seed)));
    float tears = tear_mask * tear_shape * tear_strength;

    float mono = 0.5 + (snow - 0.5) * 1.30;
    mono += bands * 0.14;
    mono += tears * 0.22;
    mono -= scan_dark * 0.34;
    mono = clamp(mono, 0.0, 1.0);

    float edge = min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y));
    float vignette = 1.0 - smoothstep(0.0, 0.22, edge);
    float alpha = overlay_strength * (0.18 + abs(mono - 0.5) * 1.06 + bands * 0.22 + tears * 0.30);
    vec3 color = vec3(mono);
    color = mix(color, vec3(0.0), vignette * vignette_strength * 0.88);
    alpha += vignette * vignette_strength * 0.07;
    alpha = clamp(alpha, 0.0, 0.46);

    // Pass 84: composite the authored tint layer and gameplay brown grade in this same
    // fullscreen pass.  This replaces three additional alpha cards and their overdraw.
    vec2 tuv = clamp(uv * tint_uv_transform.xy + tint_uv_transform.zw, vec2(0.0), vec2(1.0));
    vec4 lens = texture(tint_tex, tuv);
    float la = clamp(lens_alpha * lens.a, 0.0, 0.34);
    vec3 premul = color * alpha;
    float out_a = alpha;
    premul = lens.rgb * la + premul * (1.0 - la);
    out_a = la + out_a * (1.0 - la);
    float pa = clamp(palette_tint.a, 0.0, 0.30);
    premul = palette_tint.rgb * pa + premul * (1.0 - pa);
    out_a = pa + out_a * (1.0 - pa);
    vec3 out_rgb = (out_a > 0.0001) ? premul / out_a : vec3(0.0);
    p3d_FragColor = vec4(clamp(out_rgb,0.0,1.0), clamp(out_a,0.0,0.62));
}
