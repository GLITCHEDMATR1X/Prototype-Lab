#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ModelMatrixInverseTranspose;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;
out vec2 v_uv;
out vec3 v_world_pos;
out vec3 v_world_normal;
void main(){
 gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex;
 v_uv=p3d_MultiTexCoord0;
 v_world_pos=(p3d_ModelMatrix*p3d_Vertex).xyz;
 v_world_normal=normalize((p3d_ModelMatrixInverseTranspose*vec4(p3d_Normal,0.0)).xyz);
}
