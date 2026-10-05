# luce-webp

A WebP decoder for Luce/Base: a faithful port of libwebp 1.6.0's decoder (the version
Ladybird links), lossy, lossless, alpha and animation, giving libwebp's pixels bit for bit.
It depends on no other package: only the compiler's built-in modules. The browser engine
decodes WebP images through it.

```luce
from luce_webp import webp

let found = try webp.info(data)                # canvas, alpha, frames, loop count
let pixels = try new u8[found.width * found.height * 4] ---
try webp.decode_rgba8(data, pixels)            # straight RGBA, as WebPDecodeRGBAInto

var animation = try webp.Animation.open(data)  # `data` must outlive it
defer animation.release()
for (index, frame) in animation.frames().indexed():
    try animation.render(index, pixels)        # frame `index`, composited as WebPAnimDecoder does
    show(pixels, frame.duration)               # milliseconds, as written

if let profile = try webp.icc_profile(data):   # the ICCP chunk, as WebPMux reads it
    use(profile)                               # luce-color makes a color space of it
```

## API

- `features(data) -> Info!` (WebPGetFeatures): `width` and `height` of the canvas, `alpha`
  (the VP8X alpha flag, an ALPH chunk, or the VP8L header's alpha bit), `animated` (the VP8X
  animation flag), `format` (`lossy`, `lossless`, or `mixed` for an animation).
- `info(data) -> Info!`: the same, and for an animation `frame_count`, `loop_count` (0
  forever) and `background` (the ANIM chunk's color as written) from the demuxer; `plays()`
  is how many times it plays (0 forever, 1 for a still picture).
- `decode_rgba8(data, out, options)`: a still picture into `out` of at least
  `width * height * 4` bytes; an animation's first frame. libwebp's defaults, which Ladybird
  uses: fancy upsampling, no dithering. Alpha is straight; a picture whose `alpha` is false
  is still decoded with whatever alpha it stores (Ladybird draws such a picture opaque).
- `Animation.open(data, options) -> Animation!` (WebPAnimDecoderNew), then `frames()` and
  `render(index, out)` (WebPAnimDecoderGetNext): each `Frame` has its rectangle (`left`,
  `top`, `width`, `height`), `duration` (milliseconds as written), `disposal` (`keep`,
  `background`), `blend` and `alpha`. Frames render fastest in order; an earlier index starts
  again from the first. `release` frees the frame list and the two canvases. A still picture
  is an animation of one frame.
- `icc_profile(data) -> const u8[]?!`: the ICCP chunk's payload when the VP8X flags
  announce one; it fails where WebPMuxCreate refuses the file (inconsistent flags and
  chunks), which makes a browser refuse the image.
- `Options.max_pixels` (default 2^28) bounds the canvas.
- Errors: `corrupt` (not a WebP, damaged, or ending early), `limit`, `invalid` (an output
  buffer too small, a frame index past the last), `unsupported` (a VP8 frame that is not a
  shown key frame, an animation where a still picture is decoded).

## What is ported

From libwebp 1.6.0 (`src/dec`, `src/dsp`, `src/utils`, `src/demux`, `src/mux`): the RIFF
container and its header checks (`webp_dec.c`); VP8's boolean decoder, headers, segments,
quantizers, probabilities, intra modes and residuals, intra prediction, the inverse DCT and
WHT, the simple and complex loop filters (`vp8_dec.c`, `tree_dec.c`, `quant_dec.c`,
`frame_dec.c`, `dsp/dec.c`); the RGBA output with the fancy upsampler and alpha
(`io_dec.c`, `dsp/upsampling.c`, `dsp/yuv.h`); the ALPH chunk, raw or lossless, with its
filters (`alpha_dec.c`, `dsp/filters.c`); VP8L's bit reader, Huffman tables and groups (with
packed tables), color cache, LZ77 with 2D distances, the four transforms and byte-per-pixel
alpha (`vp8l_dec.c`, `huffman_utils.c`, `dsp/lossless.c`); the demuxer and WebPAnimDecoder
(`demux.c`, `anim_decode.c`); WebPMux's reading and validation (`muxread.c`,
`muxinternal.c`) for the ICC profile.

Left out, as Ladybird never asks for them: incremental decoding (`idec_dec.c`), cropping
and scaling (`rescaler`), YUV and premultiplied output modes, dithering (`random_utils`,
`quant_levels_dec_utils`; off by default), threads (which do not change the output), and
the encoder. EXIF and XMP chunks are skipped. libwebp decodes an ALPH chunk a few rows ahead
of the color rows; this decodes the plane at the first request, which gives the same plane
and fails where libwebp fails.

## Agreement with libwebp

`tests/run.py` compares every frame of tests/fixtures (Ladybird's 23 WebP test inputs and 83
files made with libwebp 1.6.0's cwebp, img2webp, gif2webp and webpmux, damaged ones among
them) with libwebp's output, through the C oracle in luce-browser-tools
(`oracles/luce-webp`): features, durations and an FNV-1a hash of every frame, in native, C
and diagnostic builds. Locally, the same holds on larger sets:

| Set | Files | Identical to libwebp's C build |
| --- | ---: | ---: |
| Ladybird's test inputs | 23 | 23 |
| cwebp/img2webp/gif2webp/webpmux corpus (`gen_corpus.py`) | 544 | 544 |
| Other WebP files on hand (Ladybird's other tests and UI, Krita, libvips, OIIO, resvg) | 66 | 66 |
| Mutations of the above (bytes changed, bits flipped, cut, inserted) | 4,000 | 4,000 |

The reference is libwebp's portable C code. Its NEON build (as Ladybird ships it on arm64)
agrees with it on every valid file; on 2 of the damaged files in the corpus, whose
coefficients leave the range VP8 encoders produce, NEON's saturating inverse transform gives
other pixels.

## Speed

On a 1024x772 picture (Apple M-series, native build), against libwebp built without SIMD:

| Picture | libwebp (C) | luce-webp |
| --- | ---: | ---: |
| lossy (Ladybird's 4.webp) | 9.5 ms | 17.6 ms |
| lossy with lossless alpha | 11.8 ms | 22.8 ms |
| lossless | 12.6 ms | 21.7 ms |

## Tests

```
./test.sh                                   # every compiler named: -W, fmt, tests, fixtures
LUCE_BASE_EXTRA=~/.local/bin/luce-base ./test.sh
python3 tests/run.py --expected ORACLE      # expected.txt again, from libwebp
```

## Licenses

luce-webp is MIT or Apache-2.0 (LICENSE-MIT, LICENSE-APACHE). It is a port of libwebp,
Copyright (c) 2010, Google Inc., BSD-3-Clause, with Google's patent grant (LICENSE-libwebp).
The fixtures under tests/fixtures/ladybird are Ladybird's (BSD-2-Clause, their LICENSE);
4.webp and 4-with-8-partitions.webp are a Wikimedia Commons photograph ("Frühling blühender
Kirschenbaum") under CC BY-SA 3.0, re-encoded by Google's WebP gallery.
