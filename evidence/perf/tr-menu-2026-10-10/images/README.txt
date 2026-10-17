Screenshots of the Tomb Raider main menu (848x480 Low, X11 through the
Winlator wrapper). Each one was taken after the 8 HUD samples of its run; the
HUD in the corner is DXVK's.

system_driver_run1/2.jpg
    System Mali driver. In both runs the scene is mostly black: the
    background, the logo and the level preview are not drawn as on the other
    drivers. Its 12-14 fps renders less than FourFectVK does, so it isn't a
    like-for-like target. Why it draws this way was not investigated.

fourfectvk_default.jpg, fourfectvk_no_clip_cull.jpg, fourfectvk_no_tiler_chain.jpg
    Correct picture.

fourfectvk_3switches_BROKEN_bc_tiled.jpg,
fourfectvk_no_clip_cull_3switches_BROKEN_bc_tiled.jpg
    PANVK_V9_NO_TILER_CHAIN=1 PANVK_BC_TILED=1 PAN_LATE_VECTORIZE=1:
    blocky logo, a black panel over the menu, a wrong preview. Without
    PANVK_BC_TILED the picture is correct, so that switch is the cause
    (probably tiled BC images that are also accessed through uncompressed
    views; not verified). The
    fps measured with it (6.2-6.9, 8.8-10.2) are not valid results.

fourfectvk_ubo_push.jpg, fourfectvk_ubo_push_no_clip_cull.jpg
    PANVK_UBO_PUSH=1, without and with PANVK_V9_NO_CLIP_CULL=1. Correct.

fourfectvk_tomb_raider_default_2026-10-12.jpg,
fourfectvk_tomb_raider_clip_forced_on_2026-10-12.jpg,
fourfectvk_tomb_raider_default_ubo_push_2026-10-12.jpg
    0004 build: no environment (clip distances off through the Tomb Raider
    driconf entry), pan_disable_clip_cull_distance=false, and PANVK_UBO_PUSH=1.
    Correct.
