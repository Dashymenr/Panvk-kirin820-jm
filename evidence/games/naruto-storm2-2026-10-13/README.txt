Naruto Shippuden: Ultimate Ninja Storm 2 (NSUNS2.exe), 2026-10-13
================================================================

Setup: Mali-G57 MC2, FourFectVK, Wine virtual desktop 848x480, game at
640x480. Tested on Hangover Wine 11.16 and on Proton 10.0-4 arm64ec (the
Bannerlator bionic build, v14), DXVK 1.5.5, 1.11.1-sarek and
2.3.1-gplasync, Winlator libvulkan_wrapper and another wrapper.

Symptom
-------
Device and swapchain are created (feature level 11_0), then nothing: white
(DXVK 1.x) or black (DXVK 2.x) window, GPU idle, the game at ~170% CPU
forever (10+ min). No DXVK error, no driver error. The same on Wine and on
Proton, with both wrappers, all three DXVK versions, test7 and the current
build. DXVK never compiles a graphics pipeline, so the game never draws.

Diagnosis
---------
Per-thread CPU: two game threads spin at 100%, everything else waits.
Under Hangover's FEX arm64ec the x86 RSP lives in host x23 (sp while in
arm64ec code); the guest stacks were read from /proc/<pid>/mem and the
PE images found by their MZ/PE headers (Proton maps them anonymously).

- main thread: spins in NSUNS2.exe+0x55f1a0 on
      while (!render->idle()) ;     // byte flag at +0x88 of the object
  waiting for the render thread.
- render thread (started from msvcr120): D3D11.DLL (DXVK) frames calling
  winevulkan, plus QueryPerformanceCounter (DXVK's FlushImplicit timer):
  it polls ID3D11DeviceContext::GetData on a query that never completes.
  One native sample was inside libvulkan_panfrost.so.

The game uses D3D11 TIMESTAMP / TIMESTAMP_DISJOINT queries before its first
frame. On v9 (JM) vkCmdWriteTimestamp2 was a stub and timestamp query pools
were not handled (UNREACHABLE in CreateQueryPool), so the query never
became available. The queue reports timestampValidBits = 0, but DXVK uses
timestamp queries anyway.

Fix (0005)
----------
vkCmdWriteTimestamp2 on v9 closes the current batch (the same ordering as
vkCmdEndQuery), writes the GPU system timestamp with a WRITE_VALUE job and
marks the query available; CreateQueryPool, GetQueryPoolResults and the GPU
copy kernel handle TIMESTAMP pools. Behind PANVK_V9_TIMESTAMP=1 or the
driconf option pan_v9_timestamps, off by default and on for NSUNS2.exe.
timestampValidBits stays 0. When the switch is off and an application
creates a timestamp pool, the driver logs it once.

Results (screenshots in this directory)
---------------------------------------
same build, switch off (control)        hang, black window, GPU 0%
                                        (fourfectvk_timestamps_off_hang_*.jpg)
PANVK_V9_TIMESTAMP=1, Winlator wrapper,  intro plays, 28.5-29.8 fps, GPU 55-100%
  DXVK 1.5.5, Proton 10                 (fourfectvk_timestamps_on_intro_proton10.jpg)
PANVK_V9_TIMESTAMP=1, other wrapper,     intro plays, 29.0-30.4 fps
  DXVK 2.3.1-gplasync, Proton 10
driconf only (no env), other wrapper,    intro plays, 29.8-29.9 fps; the
  DXVK 2.3.1-gplasync, Proton 10        "not supported" warning is not logged
The intro video runs at 30 fps. All runs: 0 MEM_ALLOC failures, no failed
pipelines, picture checked on screenshots.

CTS: dEQP-VK.query_pool (without statistics_query) + pipeline.monolithic.
timestamp, 666 cases: identical results with the switch off and on (386
Pass, 278 NotSupported, 2 Fail). The timestamp tests report NotSupported
because timestampValidBits is 0, so CTS does not exercise the new path;
the evidence for it is the game. The 2 failures
(query_pool.concurrent_queries.{primary,secondary}_command_buffer, occlusion
result 0 for slot 1) are the same with the switch off.

Other findings
--------------
- Hangover Wine: the game's own protection shows "Internal error 0x0A:
  Protection initialization failed!" on about every second launch. On
  Proton 10.0-4 every launch got through. Not driver related.
- Bannerlator "failed create dxgi device": the BCn layer (libbcn_layer.so,
  ENABLE_BCN_COMPUTE=1) with BCN_TRANSCODE_TO_ASTC=1 enables shaderFloat16
  and shaderInt8 at device creation without checking shaderFloat16. v9
  reports shaderFloat16 = false, so vkCreateDevice fails with
  VK_ERROR_FEATURE_NOT_PRESENT (-8) and DXVK can't create the D3D11 device.
  Reproduced here; with the ASTC transcode option off the device is created
  and the game runs.
- Not the cause (tested): pipeline statistics off (PANVK_V9_NO_STATS=1),
  reported VRAM capped to 1921 MiB (dxgi.maxDeviceMemory), the 0004 changes
  (test7 hangs the same).
