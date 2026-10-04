#version 150

uniform sampler2D p3d_Texture0;
uniform sampler2D normal_tex;
uniform sampler2D rough_tex;
uniform sampler2D height_tex;
uniform sampler2D ao_tex;
uniform vec4 p3d_ColorScale;
uniform vec4 material_tint;
uniform float alt_wall_veil_mask;
uniform float alt_wall_veil_strength;
uniform vec3 alt_wall_veil_color;

struct p3d_LightSourceParameters {
    vec4 color;
    vec3 spotDirection;
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
};
uniform p3d_LightSourceParameters shadow_key;

uniform vec3 camera_pos;
uniform vec3 fog_color;
uniform float fog_density;
uniform float fog_near;
uniform float fog_full_start;
uniform float fog_full_end;
uniform float map_scale;
uniform float normal_strength;
uniform float specular_strength;
uniform float roughness_bias;
uniform float roughness_min;
uniform float roughness_max;
uniform vec3 material_f0;
uniform float material_metalness;
uniform float reflection_strength;
uniform float parallax_strength;
uniform float ao_strength;
uniform float weathering_strength;
uniform float wetness_strength;
uniform vec3 key_light_dir;
uniform vec3 key_light_color;
uniform vec3 ambient_color;
uniform vec3 warm_light0_pos;
uniform vec3 warm_light1_pos;
uniform vec3 warm_light2_pos;
uniform vec3 warm_light3_pos;
uniform vec3 warm_light_color;
uniform float atmosphere_strength;
uniform float shader_time;
uniform vec3 dream_tint;
uniform float dream_tint_strength;
uniform float shadow_grain_strength;
uniform float player_motion;
uniform float weather_alarm;
uniform float burn_strength;
uniform float cohesion_strength;
uniform float pal_secam_grade_strength;
uniform sampler2D gi_atlas;
uniform vec4 gi_bounds;
uniform vec3 gi_heights;
uniform float gi_strength;
uniform float global_shadow_veil;
uniform float practical_light_boost;
uniform float shadow_map_strength;
uniform float shadow_softness;
uniform float shadow_height_fade_start;
uniform float shadow_height_fade_end;
uniform float display_grayscale_strength;
uniform float static_strength;
uniform float static_scale;
uniform float static_speed;
uniform vec2 static_flow_dir;
uniform float static_contrast;
uniform vec2 wind_flow;
uniform float wind_flow_strength;
uniform vec4 lens_player;
uniform vec4 lens_player_params;
uniform vec4 lens_event0;
uniform vec4 lens_event0_params;
uniform vec4 lens_event1;
uniform vec4 lens_event1_params;
uniform float lens_fragment_strength;

in vec3 v_world_pos;
in vec3 v_world_normal;
in vec4 v_color;
in vec4 v_shadow_pos;
in float v_lens_signal;
out vec4 p3d_FragColor;

vec3 weights_for(vec3 n) {
    vec3 w = pow(abs(n), vec3(7.0));
    return w / max(w.x + w.y + w.z, 0.0001);
}

vec3 triplanar_color(sampler2D tex, vec3 p, vec3 n, float scale) {
    vec3 w = weights_for(n);
    vec3 x = texture(tex, p.yz * scale).rgb;
    vec3 y = texture(tex, p.xz * scale).rgb;
    vec3 z = texture(tex, p.xy * scale).rgb;
    return x*w.x + y*w.y + z*w.z;
}

float triplanar_scalar(sampler2D tex, vec3 p, vec3 n, float scale) {
    vec3 w = weights_for(n);
    float x = texture(tex, p.yz * scale).r;
    float y = texture(tex, p.xz * scale).r;
    float z = texture(tex, p.xy * scale).r;
    return x*w.x + y*w.y + z*w.z;
}

float dominant_scalar(sampler2D tex, vec3 p, vec3 n, float scale) {
    vec3 a = abs(n);
    if (a.x >= a.y && a.x >= a.z) return texture(tex, p.yz * scale).r;
    if (a.y >= a.x && a.y >= a.z) return texture(tex, p.xz * scale).r;
    return texture(tex, p.xy * scale).r;
}

vec3 triplanar_normal(vec3 p, vec3 geom_n, float scale) {
    vec3 w = weights_for(geom_n);
    vec3 sx = texture(normal_tex, p.yz * scale).xyz * 2.0 - 1.0;
    vec3 sy = texture(normal_tex, p.xz * scale).xyz * 2.0 - 1.0;
    vec3 sz = texture(normal_tex, p.xy * scale).xyz * 2.0 - 1.0;

    vec3 nx = normalize(vec3(sign(geom_n.x) * sx.z, sx.x, sx.y));
    vec3 ny = normalize(vec3(sy.x, sign(geom_n.y) * sy.z, sy.y));
    vec3 nz = normalize(vec3(sz.x, sz.y, sign(geom_n.z) * sz.z));
    vec3 mapped = normalize(nx*w.x + ny*w.y + nz*w.z);
    return normalize(mix(geom_n, mapped, clamp(normal_strength, 0.0, 1.0)));
}


vec3 sample_pathtrace_gi(vec3 p) {
    vec2 extent = max(gi_bounds.zw - gi_bounds.xy, vec2(0.001));
    vec2 uv = clamp((p.xy - gi_bounds.xy) / extent, vec2(0.001), vec2(0.999));
    vec3 s0 = pow(texture(gi_atlas, vec2((uv.x + 0.0) / 3.0, uv.y)).rgb, vec3(2.2));
    vec3 s1 = pow(texture(gi_atlas, vec2((uv.x + 1.0) / 3.0, uv.y)).rgb, vec3(2.2));
    vec3 s2 = pow(texture(gi_atlas, vec2((uv.x + 2.0) / 3.0, uv.y)).rgb, vec3(2.2));
    if (p.z <= gi_heights.x) return s0;
    if (p.z >= gi_heights.z) return s2;
    if (p.z < gi_heights.y) {
        float t = clamp((p.z - gi_heights.x) / max(gi_heights.y - gi_heights.x, 0.001), 0.0, 1.0);
        return mix(s0, s1, t);
    }
    float t = clamp((p.z - gi_heights.y) / max(gi_heights.z - gi_heights.y, 0.001), 0.0, 1.0);
    return mix(s1, s2, t);
}


float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float fragment_lens_field(vec3 world_pos, vec4 origin_radius, vec4 params, out vec3 radial_dir) {
    float radius = origin_radius.w;
    float strength = params.x;
    radial_dir = vec3(0.0, 0.0, 1.0);
    // Pass 78: inactive lens events are the normal state. Reject them before the
    // distance/normalization work so four empty event slots cost almost nothing.
    if (radius <= 0.001 || strength <= 0.0001) return 0.0;
    vec3 delta = world_pos - origin_radius.xyz;
    float dist = length(delta);
    radial_dir = (dist > 0.0001) ? delta / dist : vec3(0.0, 0.0, 1.0);
    if (dist >= radius) return 0.0;
    float fall = 1.0 - dist / radius;
    fall = fall * fall * (3.0 - 2.0 * fall);
    if (params.w < 0.0) {
        float ripple = 0.56 + 0.44 * sin(dist * params.y - shader_time * params.z);
        return strength * fall * ripple;
    }
    float age = max(params.w, 0.0);
    float front_radius = age * params.z * 0.52;
    float front = exp(-abs(dist - front_radius) * (1.45 + params.y * 0.06));
    float ring = 0.62 + 0.38 * sin(dist * params.y - age * params.z * 1.35);
    return strength * fall * front * ring;
}

const float PI = 3.14159265359;


vec3 rgb_to_yuv(vec3 c) {
    return vec3(
        dot(c, vec3(0.29900, 0.58700, 0.11400)),
        dot(c, vec3(-0.14713, -0.28886, 0.43600)),
        dot(c, vec3(0.61500, -0.51499, -0.10001))
    );
}

vec3 yuv_to_rgb(vec3 yuv) {
    float y = yuv.x;
    float u = yuv.y;
    float v = yuv.z;
    return vec3(
        y + 1.13983 * v,
        y - 0.39465 * u - 0.58060 * v,
        y + 2.03211 * u
    );
}

vec3 apply_pal_secam_grade(vec3 input_color, float strength) {
    vec3 c = clamp(input_color, 0.0, 1.0);
    vec3 yuv = rgb_to_yuv(c);

    // Analog broadcast color carries less detail/energy than luminance.  Compress
    // chroma while keeping the high-resolution 3D luma and material response intact.
    float line_phase = (mod(floor(gl_FragCoord.y), 2.0) < 0.5) ? -1.0 : 1.0;
    float chroma_scale = 0.54 + line_phase * 0.024;
    yuv.y *= chroma_scale * (1.0 + line_phase * 0.040);
    yuv.z *= chroma_scale * (1.0 - line_phase * 0.032);

    // Small fixed U/V rotation gives the desired old PAL/SECAM conversion color drift
    // without a moving screen-space effect or NTSC-like unstable hue wobble.
    float angle = radians(-7.8);
    float cs = cos(angle);
    float sn = sin(angle);
    vec2 uv = mat2(cs, -sn, sn, cs) * yuv.yz;
    yuv.yz = uv;

    vec3 analog = clamp(yuv_to_rgb(yuv), 0.0, 1.0);
    float luma = yuv.x;

    // Slightly faded tube/broadcast transfer: lifted low end, gentler highlights,
    // olive-green/amber mids and cool restrained shadows.
    analog = analog * 0.935 + vec3(0.006, 0.007, 0.005);
    vec3 shadow_cast = vec3(0.86, 0.95, 1.01);
    vec3 mid_cast = vec3(1.050, 1.030, 0.885);
    vec3 high_cast = vec3(1.015, 0.955, 0.885);
    vec3 grade_cast = mix(shadow_cast, mid_cast, smoothstep(0.12, 0.58, luma));
    grade_cast = mix(grade_cast, high_cast, smoothstep(0.62, 0.96, luma));
    analog *= grade_cast;

    // A tiny alternating chroma density difference evokes phase-alternating / sequential
    // color reconstruction while remaining visually stable from frame to frame.
    float line_luma = line_phase * 0.0060;
    analog += vec3(line_luma * 0.30, line_luma * 0.75, -line_luma * 0.26);

    return mix(input_color, clamp(analog, 0.0, 1.0), clamp(strength, 0.0, 1.0));
}

vec3 fresnel_schlick(float cosTheta, vec3 F0) {
    float m = clamp(1.0 - cosTheta, 0.0, 1.0);
    float m5 = m*m*m*m*m;
    return F0 + (vec3(1.0) - F0) * m5;
}

float distribution_ggx(float NoH, float roughness) {
    float a = max(0.035, roughness * roughness);
    float a2 = a * a;
    float d = NoH * NoH * (a2 - 1.0) + 1.0;
    return a2 / max(PI * d * d, 0.00001);
}

float geometry_schlick_ggx(float NoX, float roughness) {
    float r = roughness + 1.0;
    float k = (r * r) * 0.125;
    return NoX / max(NoX * (1.0 - k) + k, 0.00001);
}

vec3 ggx_specular(vec3 N, vec3 V, vec3 L, vec3 F0, float roughness) {
    float NoV = max(dot(N, V), 0.001);
    float NoL = max(dot(N, L), 0.0);
    if (NoL <= 0.0) return vec3(0.0);
    vec3 H = normalize(V + L);
    float NoH = max(dot(N, H), 0.0);
    float VoH = max(dot(V, H), 0.0);
    float D = distribution_ggx(NoH, roughness);
    float G = geometry_schlick_ggx(NoV, roughness) * geometry_schlick_ggx(NoL, roughness);
    vec3 F = fresnel_schlick(VoH, F0);
    return (D * G * F / max(4.0 * NoV * NoL, 0.001)) * NoL;
}


float sample_directional_shadow(vec4 shadow_pos, float ndotl) {
    if (shadow_map_strength <= 0.001 || shadow_pos.w <= 0.0001) return 1.0;
    vec3 proj = shadow_pos.xyz / shadow_pos.w;
    if (proj.x <= 0.0 || proj.x >= 1.0 || proj.y <= 0.0 || proj.y >= 1.0 || proj.z <= 0.0 || proj.z >= 1.0) return 1.0;

    // Pass 82: three-tap triangular PCF keeps grounded close shadows while reducing
    // dependent texture lookups. Height fade below removes unstable upper-wall shadow detail.
    float bias = mix(0.00165, 0.00052, clamp(ndotl, 0.0, 1.0));
    vec2 texel = 1.0 / vec2(textureSize(shadow_key.shadowMap, 0));
    vec2 radius = texel * shadow_softness * shadow_pos.w;
    float z = shadow_pos.z - bias * shadow_pos.w;
    float sum = 0.0;
    sum += textureProj(shadow_key.shadowMap, vec4(shadow_pos.xy, z, shadow_pos.w));
    sum += textureProj(shadow_key.shadowMap, vec4(shadow_pos.xy + vec2(-0.72,-0.46)*radius, z, shadow_pos.w));
    sum += textureProj(shadow_key.shadowMap, vec4(shadow_pos.xy + vec2( 0.72, 0.46)*radius, z, shadow_pos.w));
    float visibility = sum / 3.0;
    // Shadows attenuate only the broad key; GI/ambient/practical light remain.
    visibility = mix(1.0, mix(0.48, 1.0, visibility), clamp(shadow_map_strength, 0.0, 1.0));
    return visibility;
}


float value_noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float windblown_static(vec2 p, float t) {
    vec2 base_dir = normalize(static_flow_dir + wind_flow * 0.92 + vec2(0.0001, 0.0002));
    vec2 side_dir = vec2(-base_dir.y, base_dir.x);
    float gust = 0.80 + wind_flow_strength * 0.34 + sin(t * 0.19) * 0.08;
    vec2 drift = base_dir * (t * static_speed * gust);
    vec2 uv = p * static_scale + drift;

    // Grainy TV cells plus a softer advected envelope.  Both move in the world, not the screen.
    float fine_a = hash21(floor(uv * 2.15));
    float fine_b = hash21(floor(uv * 4.70 + vec2(17.3, 5.9)));
    float fine_c = hash21(floor(uv * 7.80 + vec2(3.1, 29.4)));
    float cloud = value_noise(uv * 0.22 + base_dir * t * static_speed * 0.18);
    float cross = value_noise(vec2(dot(uv, side_dir) * 0.34, dot(uv, base_dir) * 0.10));
    float mixed_noise = fine_a * 0.40 + fine_b * 0.26 + fine_c * 0.12 + cloud * 0.15 + cross * 0.07;

    // Higher contrast than Pass 52: visible black/grey speckles, not a barely measurable tint.
    float width = mix(0.30, 0.12, clamp(static_contrast, 0.0, 1.0));
    float centered = smoothstep(0.50 - width, 0.50 + width, mixed_noise);
    return clamp(centered, 0.0, 1.0);
}

float point_light(vec3 light_pos, vec3 n, vec3 p, out vec3 L) {
    vec3 delta = light_pos - p;
    float d = length(delta);
    L = delta / max(d, 0.001);
    float attenuation = 1.0 / (1.0 + 0.045*d + 0.012*d*d);
    return max(dot(n, L), 0.0) * attenuation;
}

void main() {
    vec3 geom_n = normalize(v_world_normal);
    vec3 V = normalize(camera_pos - v_world_pos);

    // Pass 78: distance-aware material LOD. Close geometry keeps Pass 77 relief and
    // triplanar normal detail; distant megawalls use their geometric normal and skip the
    // invisible high-frequency work.  Collision/silhouette authority is unchanged.
    float view_dist = length(camera_pos - v_world_pos);
    float detail_lod = 1.0 - smoothstep(48.0, 96.0, view_dist);
    float height0 = 0.5;
    if (parallax_strength > 0.0001 && view_dist < 58.0) {
        height0 = dominant_scalar(height_tex, v_world_pos, geom_n, map_scale);
    }
    float view_facing = max(abs(dot(V, geom_n)), 0.32);
    vec3 tangent_view = V - geom_n * dot(V, geom_n);
    float tangent_len = length(tangent_view);
    if (tangent_len > 0.0001) tangent_view /= tangent_len;
    float effective_parallax = parallax_strength * detail_lod;
    vec3 material_pos = v_world_pos - tangent_view * ((height0 - 0.5) * effective_parallax / view_facing);
    vec3 n = geom_n;
    if (view_dist < 102.0) {
        vec3 mapped_n = triplanar_normal(material_pos, geom_n, map_scale);
        n = normalize(mix(geom_n, mapped_n, detail_lod));
    }

    // Pass 69: fragment-level lens response gives broad/low-poly walls and floors a visible
    // warped surface response even when there are not enough vertices for detailed displacement.
    // Pass 83: only two transient lens events are active at once. The player field plus
    // two event fields preserve the touch/gravity-lensing look without four per-fragment
    // distance evaluations on every close PBR surface.
    vec3 lr0; vec3 lr1; vec3 lrp;
    float lf = 0.0;
    lf += fragment_lens_field(v_world_pos, lens_player, lens_player_params, lrp);
    lf += fragment_lens_field(v_world_pos, lens_event0, lens_event0_params, lr0);
    lf += fragment_lens_field(v_world_pos, lens_event1, lens_event1_params, lr1);
    vec3 lens_dir = lrp + lr0 + lr1;
    if (length(lens_dir) > 0.001 && lf > 0.0001) {
        lens_dir = normalize(lens_dir);
        vec3 tangent_pull = lens_dir - n * dot(lens_dir, n);
        n = normalize(n + tangent_pull * clamp(lf * lens_fragment_strength * 1.55, 0.0, 0.30));
    }

    vec3 sampled = triplanar_color(p3d_Texture0, material_pos, geom_n, map_scale);
    vec3 tint = mix(vec3(1.0), material_tint.rgb, 0.24) * p3d_ColorScale.rgb;
    vec3 albedo = pow(max(sampled, vec3(0.0)), vec3(2.2)) * tint;
    float rough_sample = 0.5;
    if (view_dist < 92.0) {
        rough_sample = triplanar_scalar(rough_tex, material_pos, geom_n, map_scale);
    } else {
        rough_sample = dominant_scalar(rough_tex, material_pos, geom_n, map_scale);
    }
    rough_sample = clamp(rough_sample, 0.0, 1.0);
    float ao_sample = 1.0;
    if (ao_strength > 0.001 && view_dist < 72.0) {
        ao_sample = triplanar_scalar(ao_tex, material_pos, geom_n, map_scale);
    }
    float ao_factor = mix(1.0, clamp(ao_sample, 0.0, 1.0), clamp(ao_strength * detail_lod, 0.0, 1.0));
    if (static_strength > 0.001) {
        // Most architectural materials do not use moving analog grain. Do not run the
        // multi-noise wind field at all unless this material actually opts into it.
        float static_noise = windblown_static(v_world_pos.xy, shader_time);
        float static_centered = (static_noise - 0.5) * 2.0;
        float dark_part = max(-static_centered, 0.0);
        float bright_part = max(static_centered, 0.0);
        float contrast_mul = 1.0 - dark_part * static_strength * 0.54 + bright_part * static_strength * 0.42;
        albedo *= clamp(contrast_mul, 0.34, 1.48);
        // Small neutral static lift makes the brighter grains read like analog noise without glowing.
        albedo += vec3(bright_part * static_strength * 0.018);
        albedo = mix(albedo, vec3(dot(albedo, vec3(0.3333))), static_strength * 0.055 * abs(static_centered));
        rough_sample = clamp(rough_sample + static_centered * static_strength * 0.16, 0.0, 1.0);
    }
    float roughness = clamp(mix(roughness_min, roughness_max, rough_sample) + roughness_bias, 0.055, 1.0);

    // Large-scale weathering breaks repetition without baking unique textures into every wall.
    // Pass 80 adds uniform branches so far-wall LOD nodes can retain full albedo color while
    // skipping the procedural weather math entirely.
    float weather = 0.0;
    if (weathering_strength > 0.001) {
        float macro_a = hash21(floor(v_world_pos.xy * 0.085) + vec2(13.7, 4.2));
        float macro_b = hash21(floor(v_world_pos.yz * 0.11) + vec2(2.9, 18.4));
        float macro_noise = clamp(macro_a * 0.62 + macro_b * 0.38, 0.0, 1.0);
        float wallness_weather = 1.0 - abs(geom_n.z);
        float ground_grime = wallness_weather * (1.0 - smoothstep(0.35, 4.2, max(v_world_pos.z, 0.0)));
        weather = clamp(weathering_strength * (0.28 * macro_noise + 0.72 * ground_grime), 0.0, 1.0);
        albedo *= mix(vec3(1.0), vec3(0.72, 0.75, 0.66), weather * 0.34);
        roughness = clamp(roughness + weather * 0.055, 0.055, 1.0);
    }

    // Rain response belongs to the material now instead of a uniform glass sheet.
    // Far enclosure roots can disable it completely instead of paying for several sine calls.
    float wetness = 0.0;
    if (wetness_strength > 0.001) {
        float rain_facing = smoothstep(0.32, 0.90, geom_n.z);
        float pool_wave = 0.5 + 0.5 * sin(v_world_pos.x * 0.115 + sin(v_world_pos.y * 0.071) * 1.7);
        pool_wave *= 0.58 + 0.42 * (0.5 + 0.5 * sin(v_world_pos.y * 0.093 - v_world_pos.x * 0.041));
        float wet_mask = smoothstep(0.38, 0.77, pool_wave);
        wetness = clamp(wetness_strength * rain_facing * (0.34 + wet_mask * 0.66), 0.0, 0.92);
        albedo *= mix(vec3(1.0), vec3(0.72, 0.76, 0.72), wetness * 0.72);
        roughness = mix(roughness, max(0.075, roughness * 0.22), wetness);
    }
    vec3 L = normalize(-key_light_dir);
    vec3 H = normalize(L + V);
    float raw_ndotl = dot(n, L);

    // Pass 51: remove the old wrapped diffuse term that made back/side faces almost as
    // bright as lit faces.  A tighter curve now creates readable directional shade.
    float ndotl = max(raw_ndotl, 0.0);
    float key_diffuse_term = pow(ndotl, 1.24);
    float key_shadow = sample_directional_shadow(v_shadow_pos, ndotl);
    float shadow_height_keep = 1.0 - smoothstep(shadow_height_fade_start, shadow_height_fade_end, v_world_pos.z);
    key_shadow = mix(1.0, key_shadow, clamp(shadow_height_keep, 0.0, 1.0));

    float sky = 0.15 + 0.26 * max(n.z, 0.0);
    vec3 indirect_light = ambient_color * sky * mix(0.76, 1.0, ao_factor);

    // Baked GI remains a low-level bounce only.  Pass 55 deliberately reduces it so the
    // scene reads as broadly shadowed before local lights carve illumination back in.
    vec3 gi = sample_pathtrace_gi(v_world_pos);
    float gi_orient = 0.58 + 0.34 * max(n.z, 0.0);
    indirect_light += gi * gi_strength * gi_orient;

    vec3 shared_air = pow(max(fog_color, vec3(0.0)), vec3(2.2)) * vec3(0.90, 0.80, 0.64);
    float wallness = 1.0 - abs(n.z);
    indirect_light += shared_air * (0.014 + wallness * 0.028) * cohesion_strength;

    // Global shadow veil: darken the whole scene evenly instead of relying on a projected
    // shadow map.  This avoids odd ground-shape artifacts while preserving overall mood.
    indirect_light *= (1.0 - global_shadow_veil);
    vec3 key_diffuse = key_light_color * key_diffuse_term * (1.0 - global_shadow_veil * 0.10) * key_shadow;

    vec3 localL0 = vec3(0.0); vec3 localL1 = vec3(0.0);
    vec3 localL2 = vec3(0.0); vec3 localL3 = vec3(0.0);
    float warm0 = 0.0; float warm1 = 0.0; float warm2 = 0.0; float warm3 = 0.0;
    vec3 warm_diffuse = vec3(0.0);
    if (practical_light_boost > 0.001) {
        warm0 = point_light(warm_light0_pos, n, v_world_pos, localL0);
        warm1 = point_light(warm_light1_pos, n, v_world_pos, localL1);
        warm2 = point_light(warm_light2_pos, n, v_world_pos, localL2);
        warm3 = point_light(warm_light3_pos, n, v_world_pos, localL3);
        float warm_sum = (warm0 + warm1 + warm2 + warm3);
        warm_diffuse = warm_light_color * warm_sum * 1.55 * practical_light_boost;
    }

    vec3 diffuse_light = indirect_light + key_diffuse + warm_diffuse;

    // Pass 34: microfacet GGX/Fresnel instead of a generic plastic Phong highlight.
    vec3 F0 = mix(material_f0, max(albedo, vec3(0.02)), clamp(material_metalness, 0.0, 1.0));
    float NoV = max(dot(n, V), 0.001);
    vec3 key_spec = ggx_specular(n, V, L, F0, roughness) * key_light_color * specular_strength * key_shadow;
    vec3 local_spec = vec3(0.0);
    if (practical_light_boost > 0.001) {
        if (warm0 > 0.0) local_spec += ggx_specular(n, V, localL0, F0, roughness) * warm0;
        if (warm1 > 0.0) local_spec += ggx_specular(n, V, localL1, F0, roughness) * warm1;
        if (warm2 > 0.0) local_spec += ggx_specular(n, V, localL2, F0, roughness) * warm2;
        if (warm3 > 0.0) local_spec += ggx_specular(n, V, localL3, F0, roughness) * warm3;
    }

    // Stronger orientation/contact shading gives walls, undersides and recesses weight.
    float upward = max(n.z, 0.0);
    float cavity = mix(0.70, 1.0, clamp(0.18 + upward * 0.62 + abs(n.z) * 0.14, 0.0, 1.0)) * mix(0.74, 1.0, ao_factor);
    float diffuse_keep = 1.0 - clamp(material_metalness, 0.0, 1.0) * 0.92;
    vec3 lit = albedo * diffuse_light * cavity * diffuse_keep;
    lit += key_spec;
    lit += warm_light_color * local_spec * specular_strength * practical_light_boost;

    // Low-cost environment reflection proxy.  It uses the same atmospheric colors and
    // warm-light family as the scene, so concrete gets a broad grazing sheen, wet ground
    // gets a stronger response, and glass reads as reflective without a permanent 6x
    // dynamic cube-map render cost.
    vec3 env = shared_air;
    if (reflection_strength > 0.001) {
        vec3 R = reflect(-V, n);
        vec3 env_ground = vec3(0.040, 0.026, 0.012);
        vec3 env_side = shared_air * 0.64 + warm_light_color * 0.070;
        vec3 env_sky = shared_air * 1.24 + key_light_color * 0.10;
        float up_mix = smoothstep(-0.10, 0.72, R.z);
        float down_mix = 1.0 - smoothstep(-0.72, 0.16, R.z);
        float azimuth = 0.5 + 0.5 * sin(atan(R.y, R.x) * 2.0 + 0.55);
        env_side *= mix(0.84, 1.14, azimuth);
        env = mix(env_side, env_sky, up_mix);
        env = mix(env, env_ground, down_mix * 0.76);
        env = mix(env, shared_air, roughness * 0.72);
        vec3 view_fresnel = fresnel_schlick(NoV, F0);
        float env_energy = reflection_strength * (1.0 + wetness * 1.85) * mix(0.96, 0.26, roughness);
        env_energy *= mix(0.62, 1.0, key_shadow);
        lit += env * view_fresnel * env_energy;
    }

    // Pass 68: interaction lensing slightly boosts specular energy and compresses local tone so
    // the affected surface feels like a disturbed membrane rather than a pure rubber deformation.
    if (v_lens_signal > 0.001 || lf > 0.001) {
        float lens = clamp(max(v_lens_signal, lf * lens_fragment_strength * 5.0), 0.0, 1.0);
        lit += env * lens * 0.18;
        lit += vec3(lens * 0.028);
        lit = mix(lit, lit * vec3(0.86, 0.89, 0.95), lens * 0.12);
    }

    // Pass 07 fog-integrity model.  Atmospheric extinction begins beyond the near neighborhood,
    // then is forced to the exact clear/fog color before the camera far plane.  This guarantees
    // that distant texture seams, mesh ends and the far clip cannot remain visible through haze.
    float dist = length(camera_pos - v_world_pos);
    float height_factor = 1.0 + clamp((v_world_pos.z - 8.0) / 90.0, 0.0, 0.32);
    float noise = sin(v_world_pos.x*0.031 + v_world_pos.y*0.017 + shader_time*0.012) * 0.020;
    float atmospheric_distance = max(dist - fog_near, 0.0);
    float exponential_fog = 1.0 - exp(-fog_density * atmospheric_distance * height_factor * atmosphere_strength * (1.0 + noise));
    float opaque_guard = smoothstep(fog_full_start, fog_full_end, dist) * atmosphere_strength;
    float fog = clamp(max(exponential_fog, opaque_guard), 0.0, 1.0);

    // Slight green-gray aerial grading increases with distance without crushing nearby house color.
    vec3 graded_fog = pow(max(fog_color, vec3(0.0)), vec3(2.2)) * (1.0 + vec3(0.045, 0.005, -0.060));
    float base_luma = dot(lit, vec3(0.2126, 0.7152, 0.0722));
    float darkness = clamp(1.0 - base_luma * 1.06, 0.0, 1.0);

    // Pass 33: warm color-burn grading.  Keep the world-space dream character, but make
    // the image feel heat-stained and chemically aged rather than faded.
    float mono = dot(lit, vec3(0.299, 0.587, 0.114));
    vec3 dream_grade = vec3(mono) * dream_tint;
    float shadow_weight = smoothstep(0.36, 0.96, darkness);
    float highlight = smoothstep(0.42, 0.96, mono);
    vec3 burn_shadow = vec3(0.30, 0.18, 0.06);
    vec3 ember_tint = vec3(0.82, 0.58, 0.22);
    lit = mix(lit, dream_grade, clamp(dream_tint_strength * (0.28 + shadow_weight * 0.72), 0.0, 0.22));
    lit = mix(lit, burn_shadow * max(mono, 0.10), shadow_weight * burn_strength * 0.20);
    lit *= mix(vec3(1.0), ember_tint, burn_strength * (0.08 + shadow_weight * 0.16));
    lit = mix(lit, vec3(mono), 0.020 + shadow_weight * 0.028);
    lit = mix(lit, lit * vec3(1.05, 0.97, 0.88), highlight * burn_strength * 0.08);

    // World-locked shadow patina: spatially irregular but never translating across the screen.
    vec2 grain_cell_a = floor(v_world_pos.xy * 2.35 + v_world_pos.zz * vec2(.21,.13));
    vec2 grain_cell_b = floor(v_world_pos.yz * 3.75 + v_world_pos.xx * vec2(.09,.17));
    float n1 = hash21(grain_cell_a);
    float n2 = hash21(grain_cell_b + vec2(19.7, 7.3));
    float rough = abs((n1 * 0.62 + n2 * 0.38) - 0.5) * 2.0;
    float breathe = 0.86 + 0.14 * sin(shader_time * 0.31 + n1 * 6.2831853);
    float patina = rough * shadow_grain_strength * shadow_weight * (0.72 + player_motion * 0.20) * breathe;
    // Darkening-only: no bright speckles in the shadows.
    lit *= 1.0 - patina * vec3(0.72, 0.78, 0.86);

    // Event tint remains understated; colored rain and social moments do most of the storytelling.
    vec3 alert_grade = vec3(lit.r * 1.01, lit.g * 0.84, lit.b * 0.76);
    lit = mix(lit, alert_grade, weather_alarm * shadow_weight * 0.12);

    vec3 color = mix(lit, graded_fog, fog);
    color *= 0.82;

    // Color-burn style finishing pass: darker amber-brown mids/shadows and a slightly
    // scorched photographic feel, while keeping masks and navigation readable.
    vec3 burn_blend = vec3(0.94, 0.82, 0.66);
    vec3 burned = 1.0 - clamp((1.0 - color) / max(burn_blend, vec3(0.001)), 0.0, 1.0);
    float burn_mask = clamp(0.10 + shadow_weight * 0.90, 0.0, 1.0) * burn_strength;
    color = mix(color, burned, burn_mask * 0.52);
    color = mix(color, color * vec3(0.98, 0.95, 0.90), highlight * burn_strength * 0.05);

    color = color / (color + vec3(1.0));
    color = pow(max(color, vec3(0.0)), vec3(1.0 / 2.2));
    color = mix(color, vec3(dot(color, vec3(0.299, 0.587, 0.114))) * vec3(0.92, 0.82, 0.66), 0.04);
    color = apply_pal_secam_grade(color, pal_secam_grade_strength);
    float gray = dot(color, vec3(0.299, 0.587, 0.114));
    vec3 gray_rgb = vec3(gray);
    gray_rgb = mix(gray_rgb * 0.84, gray_rgb * 1.08, smoothstep(0.18, 0.72, gray));
    color = mix(color, clamp(gray_rgb, 0.0, 1.0), clamp(display_grayscale_strength, 0.0, 1.0));

    // Pass 138: normalize the pale Alt-Limbo wall treatment in material space rather
    // than by stacking transparent coplanar cards.  The mask is assigned only to real
    // architectural wall materials; unlit windows/emissive panes never enter this path.
    // A fixed world-space modulation keeps the veil organic but perfectly stable as the
    // camera moves, eliminating the flicker risk of near-coplanar overlay geometry.
    float veil_wallness = 1.0 - smoothstep(0.16, 0.64, abs(geom_n.z));
    float veil_cell = value_noise(v_world_pos.xy * 0.018 + v_world_pos.zz * vec2(0.011, 0.017));
    float veil_shape = 0.84 + veil_cell * 0.16;
    float veil_amount = clamp(alt_wall_veil_strength * alt_wall_veil_mask * veil_wallness * veil_shape, 0.0, 0.18);
    vec3 veil_color = clamp(alt_wall_veil_color, vec3(0.0), vec3(1.0));
    color = mix(color, veil_color, veil_amount);
    p3d_FragColor = vec4(color, v_color.a * p3d_ColorScale.a);
}
