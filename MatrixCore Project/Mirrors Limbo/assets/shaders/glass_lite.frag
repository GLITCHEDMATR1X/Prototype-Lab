#version 150
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec4 material_tint;
uniform float glass_opacity;
uniform vec3 camera_pos;
uniform vec3 fog_color;
uniform float fog_density;
uniform float fog_near;
uniform float fog_full_start;
uniform float fog_full_end;
uniform float atmosphere_strength;
uniform vec3 dream_tint;
uniform float dream_tint_strength;
in vec2 v_uv;
in vec3 v_world_pos;
in vec3 v_world_normal;
out vec4 p3d_FragColor;
void main(){
 vec3 N=normalize(v_world_normal); vec3 V=normalize(camera_pos-v_world_pos);
 float NoV=max(abs(dot(N,V)),0.0); float fres=pow(1.0-NoV,5.0);
 vec3 tex=pow(max(texture(p3d_Texture0,v_uv).rgb,vec3(0.0)),vec3(2.2));
 vec3 base=tex*mix(vec3(1.0),material_tint.rgb,0.30)*p3d_ColorScale.rgb;
 vec3 reflected=pow(max(fog_color,vec3(0.0)),vec3(2.2))*vec3(0.92,0.82,0.68)+vec3(0.035,0.025,0.014);
 vec3 lit=mix(base,reflected,0.18+fres*0.48);
 float mono=dot(lit,vec3(0.299,0.587,0.114));
 lit=mix(lit,vec3(mono)*dream_tint,clamp(dream_tint_strength*0.28,0.0,0.08));
 float dist=length(camera_pos-v_world_pos); float ad=max(dist-fog_near,0.0);
 float fog=max(1.0-exp(-fog_density*ad*atmosphere_strength),smoothstep(fog_full_start,fog_full_end,dist)*atmosphere_strength);
 vec3 fogc=pow(max(fog_color,vec3(0.0)),vec3(2.2)); lit=mix(lit,fogc,clamp(fog,0.0,1.0));
 lit=pow(max(lit,vec3(0.0)),vec3(1.0/2.2));
 float alpha=clamp(glass_opacity*(0.72+fres*0.62),0.025,0.38);
 p3d_FragColor=vec4(lit,alpha);
}
