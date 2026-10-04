#version 120
uniform vec3 sketch_light_dir_view;
uniform float fog_density;
uniform vec4 fog_color;
uniform float soft_start;
uniform float soft_end;
uniform float shadow_texel_size;
uniform float shadow_softness;
// Pass 44: ink-edge strength per node (actors 1.0, terrain lower so the ground never turns to ink)
uniform float edge_ink;
// Pass 45: fog takes the colour of the sky behind the object (horizon -> zenith), so things
// standing up into the sky are blanketed by the same haze instead of turning into pale
// cut-outs.  fog_floor keeps a faint ghost of very far landmarks (0 = none).
uniform vec4 fog_zenith;
uniform vec3 view_up;
uniform float fog_floor;
// Pass 46: distance where the streamed ground ends; the fog is total there, so the edge of
// the world is never visible (the world has no edge you can see, only haze).
uniform float fog_end;
// Pass 59: Indigo's night glow. Two soft indigo lights (Indigo's own, and the faint aura of a
// player carrying some of it): xyz = centre in view space, w = reach in metres; rgb = colour x
// strength (0 = off). glow_self makes a body radiate (Indigo at night, the charged player).
uniform vec4 glow_pos_view;
uniform vec4 glow_color;
uniform vec4 glow2_pos_view;
uniform vec4 glow2_color;
uniform float glow_self;
uniform vec3 glow_receive;              // which lights fall on this body: x Indigo's, y the player's, z the red one's
                                        // (a glowing giant is not lit by its own light)
// Pass 60: the red one's crimson light at night, and the colour a glowing body radiates
uniform vec4 glow3_pos_view;
uniform vec4 glow3_color;
uniform vec3 glow_tint;

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

varying vec4 v_color;
varying vec3 v_view_normal;
varying float v_view_distance;
varying vec4 v_shadow_coord;
varying vec3 v_view_pos;

vec3 glow_light(vec4 pos_view, vec4 colour, vec3 n, vec3 base){
    if (colour.a <= 0.0) return vec3(0.0);
    vec3 to = pos_view.xyz - v_view_pos;
    float d = length(to);
    float fall = clamp(1.0 - d / max(pos_view.w, 0.001), 0.0, 1.0);
    fall *= fall;
    float facing = 0.35 + 0.65 * max(dot(n, to / max(d, 0.001)), 0.0);   // the side facing it is lit most
    return (base * 0.8 + 0.2) * colour.rgb * fall * facing;
}

float band_value(float ndl){
    if (ndl > 0.82) return 1.00;
    if (ndl > 0.52) return 0.84;
    if (ndl > 0.24) return 0.68;
    return 0.54;
}

float shadow_tap(vec4 sc, vec2 texel_offset){
    vec4 tap = sc;
    tap.xy += texel_offset * shadow_texel_size * shadow_softness * sc.w;
    return shadow2DProj(p3d_LightSource[0].shadowMap, tap).r;
}

float sample_shadow(){
    vec4 sc = v_shadow_coord;
    if (sc.w <= 0.0001) return 1.0;
    vec3 uvz = sc.xyz / sc.w;
    if (uvz.x < 0.0 || uvz.x > 1.0 || uvz.y < 0.0 || uvz.y > 1.0 || uvz.z < 0.0 || uvz.z > 1.0) return 1.0;
    // Small receiver bias avoids self-shadow acne while keeping contact shadows attached.
    sc.z -= 0.0016 * sc.w;
    // 9-tap percentage-closer filtering. Only the cast-shadow edge is softened;
    // the scene itself is not blurred.
    float s = 0.0;
    s += shadow_tap(sc, vec2(-1.0, -1.0));
    s += shadow_tap(sc, vec2( 0.0, -1.0));
    s += shadow_tap(sc, vec2( 1.0, -1.0));
    s += shadow_tap(sc, vec2(-1.0,  0.0));
    s += shadow_tap(sc, vec2( 0.0,  0.0));
    s += shadow_tap(sc, vec2( 1.0,  0.0));
    s += shadow_tap(sc, vec2(-1.0,  1.0));
    s += shadow_tap(sc, vec2( 0.0,  1.0));
    s += shadow_tap(sc, vec2( 1.0,  1.0));
    return s / 9.0;
}

void main() {
    vec3 n = normalize(v_view_normal);
    float ndl = max(dot(n, normalize(sketch_light_dir_view)), 0.0);
    float shadow = sample_shadow();
    float shade = band_value(ndl);
    // Keep the sketch language: a cast shadow suppresses a light band rather than adding realistic soft shading.
    shade *= mix(0.52, 1.0, shadow);
    vec3 base = v_color.rgb;
    vec3 lit = base * shade;
    vec3 paper = vec3(0.96, 0.94, 0.90);
    vec3 final_rgb = mix(lit, paper * lit, 0.12);

    float softness = smoothstep(soft_start, soft_end, v_view_distance);
    // Pass 44: facing ratio against the real view ray (perspective-correct).  Using the
    // view-space n.z alone inked all ground seen at a low camera pitch.
    float nz = abs(dot(n, normalize(-v_view_pos)));
    float edge = 1.0 - smoothstep(0.16, 0.28, nz);
    float edge_strength = edge * 0.92 * (1.0 - softness * 0.92) * edge_ink;
    final_rgb = mix(final_rgb, vec3(0.04, 0.04, 0.045), edge_strength);

    // Pass 44: the far wash keeps the lit value instead of dropping to 76% of the base colour,
    // which drew a dark smudge across the middle distance before the fog lifted it again.
    vec3 soft_tone = mix(final_rgb * 0.96, paper * 0.88, 0.22);
    final_rgb = mix(final_rgb, soft_tone, softness * 0.48);

    // Pass 59: the glow lights what is near it, and a glowing body radiates (brightest at its rim)
    final_rgb += glow_light(glow_pos_view, glow_color, n, base) * glow_receive.x
               + glow_light(glow2_pos_view, glow2_color, n, base) * glow_receive.y
               + glow_light(glow3_pos_view, glow3_color, n, base) * glow_receive.z;
    if (glow_self > 0.0) {
        final_rgb = mix(final_rgb, final_rgb * 0.6 + glow_tint * 0.5, 0.42 * glow_self);
        final_rgb += glow_tint * edge * 0.75 * glow_self;
    }

    float x = fog_density * v_view_distance;
    float visibility = clamp(exp(-(x * x)), 0.0, 1.0) * (1.0 - smoothstep(fog_end * 0.78, fog_end, v_view_distance));
    visibility = max(visibility, fog_floor);
    visibility = max(visibility, 0.45 * glow_self);          // Pass 59: a glowing giant shows through the night haze
    float up = dot(normalize(v_view_pos), view_up);
    vec3 haze = mix(fog_color.rgb, fog_zenith.rgb, pow(smoothstep(0.015, 1.0, up), 0.55));
    final_rgb = mix(haze, final_rgb, visibility);
    gl_FragColor = vec4(final_rgb, v_color.a);
}
