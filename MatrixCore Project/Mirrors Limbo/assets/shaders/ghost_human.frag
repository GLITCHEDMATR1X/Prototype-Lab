#version 150

uniform vec3 camera_pos;
uniform vec3 fog_color;
uniform float fog_near;
uniform float fog_full_start;
uniform float fog_full_end;
uniform float atmosphere_strength;
uniform float shader_time;
uniform float ghost_phase;
uniform float pal_secam_grade_strength;

in vec3 v_world_pos;
in vec3 v_world_normal;
in vec3 v_local_pos;
in float v_lens_signal;
out vec4 p3d_FragColor;

float hash31(vec3 p) {
    p = fract(p * 0.1031);
    p += dot(p, p.yzx + 33.33);
    return fract((p.x + p.y) * p.z);
}


vec3 apply_pal_secam_mono_grade(vec3 c, float strength) {
    vec3 base = clamp(c, 0.0, 1.0);
    float y = dot(base, vec3(0.299, 0.587, 0.114));
    float line_phase = (mod(floor(gl_FragCoord.y), 2.0) < 0.5) ? -1.0 : 1.0;
    vec3 analog = vec3(y) * vec3(0.950, 0.990, 0.940);
    analog = analog * 0.945 + vec3(0.010, 0.012, 0.008);
    analog += vec3(0.0035, 0.0048, -0.0020) * line_phase;
    return mix(base, clamp(analog, 0.0, 1.0), clamp(strength, 0.0, 1.0));
}

void main() {
    vec3 n = normalize(v_world_normal);
    vec3 v = normalize(camera_pos - v_world_pos);
    float fresnel = pow(1.0 - max(dot(n, v), 0.0), 2.2);

    // Quantized temporal static crawls over the human surface itself, never over the screen.
    float tick = floor(shader_time * 11.0 + ghost_phase * 3.0);
    vec3 cell = floor(v_local_pos * vec3(43.0, 31.0, 58.0) + vec3(ghost_phase * 7.0, tick, tick * 0.37));
    float grain = hash31(cell);
    float coarse = hash31(floor(v_local_pos * vec3(12.0, 9.0, 18.0)) + vec3(tick * .13, ghost_phase, tick * .07));
    float white_static = smoothstep(0.84, 0.995, grain) * (0.38 + coarse * 0.62);
    float dark_static = smoothstep(0.05, 0.34, grain);

    // Near-black ghost body with sparse monochrome static and a soft silver silhouette edge.
    vec3 body = vec3(0.018, 0.020, 0.022);
    body += vec3(0.15) * dark_static * 0.18;
    body = mix(body, vec3(0.72, 0.75, 0.76), white_static * 0.70);
    body += vec3(0.23, 0.25, 0.26) * fresnel * 0.42;
    if (v_lens_signal > 0.001) {
        float lens = clamp(v_lens_signal, 0.0, 1.0);
        body += vec3(0.30, 0.33, 0.35) * lens * (0.18 + fresnel * 0.20);
    }

    float dist = length(camera_pos - v_world_pos);
    float fog = smoothstep(fog_near, fog_full_end, dist) * atmosphere_strength;
    fog = max(fog, smoothstep(fog_full_start, fog_full_end, dist) * atmosphere_strength);
    body = mix(body, pow(max(fog_color, vec3(0.0)), vec3(1.0/2.2)), clamp(fog,0.0,1.0));

    float alpha = 0.60 + fresnel * 0.10 + white_static * 0.06;
    alpha *= 1.0 - fog * 0.48;
    body = apply_pal_secam_mono_grade(body, pal_secam_grade_strength * 0.72);
    p3d_FragColor = vec4(clamp(body,0.0,1.0), clamp(alpha,0.38,0.72));
}
