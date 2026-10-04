#version 120
// Pass 44 sky dome: the model-space position is the world view direction (compass node).
uniform mat4 p3d_ModelViewProjectionMatrix;
attribute vec4 p3d_Vertex;
varying vec3 v_dir;

void main() {
    v_dir = p3d_Vertex.xyz;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
