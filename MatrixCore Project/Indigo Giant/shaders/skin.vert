#version 120
// Pass 45: sketch.vert plus GPU skinning for the characters (see skinned_actor.py).
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat3 p3d_NormalMatrix;
// Node colour scale (setColorScale). Needed for footprint wind-fade and plant glow;
// without it Panda's colour scale never reaches a custom GLSL shader.
uniform vec4 p3d_ColorScale;

struct p3d_LightSourceParameters {
    vec4 color;
    vec4 ambient;
    vec4 diffuse;
    vec4 specular;
    vec4 position;
    vec3 spotDirection;
    float spotExponent;
    float spotCutoff;
    float spotCosCutoff;
    float constantAttenuation;
    float linearAttenuation;
    float quadraticAttenuation;
    vec3 attenuation;
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
};
uniform p3d_LightSourceParameters p3d_LightSource[1];

attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec4 p3d_Color;
attribute vec4 skin_joints;
attribute vec4 skin_weights;
uniform mat4 joint_mats[65];
varying vec4 v_color;
varying vec3 v_view_normal;
varying float v_view_distance;
varying vec4 v_shadow_coord;
varying vec3 v_view_pos;

void main() {
    mat4 skin = joint_mats[int(skin_joints.x + 0.5)] * skin_weights.x
              + joint_mats[int(skin_joints.y + 0.5)] * skin_weights.y
              + joint_mats[int(skin_joints.z + 0.5)] * skin_weights.z
              + joint_mats[int(skin_joints.w + 0.5)] * skin_weights.w;
    vec4 vertex = skin * p3d_Vertex;
    vec3 normal = mat3(skin[0].xyz, skin[1].xyz, skin[2].xyz) * p3d_Normal;
    vec4 view_pos = p3d_ModelViewMatrix * vertex;
    gl_Position = p3d_ModelViewProjectionMatrix * vertex;
    v_view_normal = normalize(p3d_NormalMatrix * normal);
    v_view_distance = length(view_pos.xyz);
    v_view_pos = view_pos.xyz;
    v_color = p3d_Color * p3d_ColorScale;
    v_shadow_coord = p3d_LightSource[0].shadowViewMatrix * view_pos;
}
