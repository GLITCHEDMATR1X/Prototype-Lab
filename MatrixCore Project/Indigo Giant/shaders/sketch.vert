#version 120
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
varying vec4 v_color;
varying vec3 v_view_normal;
varying float v_view_distance;
varying vec4 v_shadow_coord;
varying vec3 v_view_pos;

void main() {
    vec4 view_pos = p3d_ModelViewMatrix * p3d_Vertex;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_view_normal = normalize(p3d_NormalMatrix * p3d_Normal);
    v_view_distance = length(view_pos.xyz);
    v_view_pos = view_pos.xyz;
    v_color = p3d_Color * p3d_ColorScale;
    v_shadow_coord = p3d_LightSource[0].shadowViewMatrix * view_pos;
}
