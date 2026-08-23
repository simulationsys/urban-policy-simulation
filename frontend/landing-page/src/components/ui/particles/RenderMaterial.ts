import * as THREE from 'three';

const renderVertexShader = `
  uniform sampler2D positions;
  uniform float uPointSize;
  varying vec3 vColor;

  void main() {
    vec3 pos = texture2D(positions, position.xy).xyz;

    // Use position to create a nice color gradient (White and Purple)
    vec3 colorA = vec3(1.0, 1.0, 1.0); // White
    vec3 colorB = vec3(0.88, 0.25, 0.98); // Light Purple
    vec3 colorC = vec3(0.29, 0.08, 0.55); // Deep Purple
    vec3 colorD = vec3(0.9, 0.8, 1.0); // Pale Purple/White

    float mixValue = smoothstep(-2.0, 2.0, pos.x);
    vec3 col1 = mix(colorA, colorB, mixValue);
    vec3 col2 = mix(colorC, colorD, smoothstep(-2.0, 2.0, pos.y));
    
    vColor = mix(col1, col2, smoothstep(-2.0, 2.0, pos.z));

    vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mvPosition;
    
    // Attenuate point size based on depth (z)
    gl_PointSize = uPointSize * (10.0 / -mvPosition.z);
  }
`;

const renderFragmentShader = `
  varying vec3 vColor;

  void main() {
    // Make the particles circular with soft edges
    vec2 coord = gl_PointCoord - vec2(0.5);
    float dist = length(coord);
    if(dist > 0.5) discard;
    
    float alpha = smoothstep(0.5, 0.1, dist);

    gl_FragColor = vec4(vColor, alpha * 0.4);
  }
`;

export class RenderMaterial extends THREE.ShaderMaterial {
  constructor() {
    super({
      vertexShader: renderVertexShader,
      fragmentShader: renderFragmentShader,
      uniforms: {
        positions: { value: null },
        uPointSize: { value: 1.2 }
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
  }
}
