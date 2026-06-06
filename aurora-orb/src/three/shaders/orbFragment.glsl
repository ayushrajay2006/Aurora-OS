uniform vec3 u_stateColor;
uniform vec3 u_glowColor;
uniform float u_opacity;
uniform float u_time;
uniform float u_amplitude;
uniform float u_isVerifying;

varying vec3 vNormal;
varying vec3 vPosition;

void main() {
  vec3 viewDir = normalize(cameraPosition - vPosition);
  float fresnel = pow(1.0 - dot(viewDir, vNormal), 3.0);

  vec3 surface = mix(u_stateColor * 0.4, u_stateColor, fresnel);
  vec3 glow = u_glowColor * fresnel * (1.5 + u_amplitude * 2.0);
  
  if (u_isVerifying > 0.5) {
      // Add a horizontal scanning glow
      float scanScan = sin(vPosition.y * 15.0 - u_time * 8.0);
      glow += u_glowColor * max(0.0, scanScan) * 0.5;
  }

  vec3 color = surface + glow;
  gl_FragColor = vec4(color, u_opacity * (0.8 + fresnel * 0.2));
}
