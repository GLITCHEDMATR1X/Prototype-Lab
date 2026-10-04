#version 150

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ModelMatrixInverseTranspose;
uniform float shader_time;
uniform vec4 lens_player;
uniform vec4 lens_player_params;
uniform vec4 lens_event0;
uniform vec4 lens_event0_params;
uniform vec4 lens_event1;
uniform vec4 lens_event1_params;

in vec4 p3d_Vertex;
in vec3 p3d_Normal;

out vec3 v_world_pos;
out vec3 v_world_normal;
out vec3 v_local_pos;
out float v_lens_signal;

float ghost_lens(vec3 world_pos, vec4 origin_radius, vec4 params) {
    float radius = origin_radius.w;
    float strength = params.x;
    if (radius <= 0.001 || strength <= 0.0001) return 0.0;
    float dist = distance(world_pos, origin_radius.xyz);
    if (dist >= radius) return 0.0;
    float fall = 1.0 - dist / radius;
    fall = fall * fall * (3.0 - 2.0 * fall);
    if (params.w < 0.0) {
        return strength * fall * (0.55 + 0.45 * sin(dist * params.y - shader_time * params.z));
    }
    float age = max(params.w, 0.0);
    float front_radius = age * params.z * 0.52;
    float front = exp(-abs(dist - front_radius) * (1.40 + params.y * 0.055));
    return strength * fall * front * (0.65 + 0.35 * sin(dist * params.y - age * params.z * 1.35));
}

mat3 rotY(float a) {
    float s = sin(a);
    float c = cos(a);
    return mat3(
        c, 0.0, s,
        0.0, 1.0, 0.0,
        -s, 0.0, c
    );
}

void main() {
    vec3 pos = p3d_Vertex.xyz;
    vec3 nrm = p3d_Normal;

    // Procedural relaxed-arm pose for the static Anatomic ghost body.
    // Bend only the outer upper-body regions so the attendants rest more naturally.
    float arm_side = sign(pos.x);
    float arm_zone = smoothstep(0.24, 0.46, abs(pos.x)) * (1.0 - smoothstep(0.70, 1.62, pos.z));
    float forearm_zone = smoothstep(0.42, 0.78, abs(pos.x)) * (1.0 - smoothstep(0.62, 1.52, pos.z));
    float bend = max(arm_zone * 0.55, forearm_zone);
    float angle = radians(32.0) * arm_side * bend;
    vec3 shoulder = vec3(0.34 * arm_side, 0.0, 1.33);
    mat3 r = rotY(angle);
    pos = mix(pos, shoulder + r * (pos - shoulder), bend);
    nrm = normalize(mix(nrm, r * nrm, bend));

    vec4 local_pre = vec4(pos, 1.0);
    vec3 world_pre = (p3d_ModelMatrix * local_pre).xyz;
    float lens = 0.0;
    lens += ghost_lens(world_pre, lens_player, lens_player_params);
    lens += ghost_lens(world_pre, lens_event0, lens_event0_params);
    lens += ghost_lens(world_pre, lens_event1, lens_event1_params);
    lens = clamp(lens, -0.22, 0.22);
    pos += nrm * lens * 0.78;

    vec4 local_pos4 = vec4(pos, 1.0);
    gl_Position = p3d_ModelViewProjectionMatrix * local_pos4;
    v_world_pos = (p3d_ModelMatrix * local_pos4).xyz;
    v_world_normal = normalize((p3d_ModelMatrixInverseTranspose * vec4(nrm, 0.0)).xyz);
    v_local_pos = pos;
    v_lens_signal = clamp(abs(lens) * 12.0, 0.0, 1.0);
}
