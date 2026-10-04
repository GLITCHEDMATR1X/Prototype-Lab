#version 150

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
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
in vec4 p3d_Color;

struct p3d_LightSourceParameters {
    vec4 color;
    vec3 spotDirection;
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
};
uniform p3d_LightSourceParameters shadow_key;

out vec3 v_world_pos;
out vec3 v_world_normal;
out vec4 v_color;
out vec4 v_shadow_pos;
out float v_lens_signal;

float lens_influence(vec3 world_pos, vec4 origin_radius, vec4 params) {
    float radius = origin_radius.w;
    float strength = params.x;
    if (radius <= 0.001 || strength <= 0.0001) return 0.0;
    float dist = distance(world_pos, origin_radius.xyz);
    if (dist >= radius) return 0.0;
    float fall = 1.0 - dist / radius;
    fall = fall * fall * (3.0 - 2.0 * fall);

    // Negative age marks the persistent player/contact field. Event fields use age to
    // create one expanding pressure ring instead of an endlessly swimming sine wave.
    if (params.w < 0.0) {
        float ripple = 0.54 + 0.46 * sin(dist * params.y - shader_time * params.z);
        return strength * fall * ripple;
    }

    float age = max(params.w, 0.0);
    float front_radius = age * params.z * 0.52;
    float front = exp(-abs(dist - front_radius) * (1.35 + params.y * 0.055));
    float ring = 0.64 + 0.36 * sin(dist * params.y - age * params.z * 1.35);
    float core = exp(-dist * 1.15) * max(0.0, 1.0 - age * 0.82);
    return strength * fall * (front * ring + core * 0.34);
}

void main() {
    vec3 world_pos_pre = (p3d_ModelMatrix * p3d_Vertex).xyz;
    float disp = 0.0;
    disp += lens_influence(world_pos_pre, lens_player, lens_player_params);
    disp += lens_influence(world_pos_pre, lens_event0, lens_event0_params);
    disp += lens_influence(world_pos_pre, lens_event1, lens_event1_params);
    disp = clamp(disp, -0.34, 0.34);
    vec4 displaced_vertex = p3d_Vertex + vec4(p3d_Normal * disp, 0.0);
    gl_Position = p3d_ModelViewProjectionMatrix * displaced_vertex;
    v_world_pos = (p3d_ModelMatrix * displaced_vertex).xyz;
    v_world_normal = normalize((p3d_ModelMatrixInverseTranspose * vec4(p3d_Normal, 0.0)).xyz);
    v_color = p3d_Color;
    vec4 view_pos = p3d_ModelViewMatrix * displaced_vertex;
    v_shadow_pos = shadow_key.shadowViewMatrix * view_pos;
    v_lens_signal = clamp(abs(disp) * 10.0, 0.0, 1.0);
}
