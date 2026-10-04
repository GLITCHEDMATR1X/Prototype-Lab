Optional loading-screen planet texture slot
==========================================

To replace the generated boot/loading Enceladus surface, place a 2:1 equirectangular image here named:

  loading_planet_wrap.png

Also accepted:

  loading_planet_wrap.jpg
  loading_planet_wrap.jpeg
  loading_planet_wrap.webp
  enceladus_boot_wrap.png
  enceladus_boot_wrap.jpg
  enceladus_boot_wrap.jpeg
  enceladus_boot_wrap.webp

Recommended size: 2048x1024 or 4096x2048.

The game wraps this image once over the 3D loading-screen moon and applies the existing spherical lighting, rim glow, and loading shadow reveal. If no file is present, the procedural Enceladus fallback is used.
