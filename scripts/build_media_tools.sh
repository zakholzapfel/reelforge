#!/usr/bin/env bash
# Build on the target OS. On Windows use MSYS2 MINGW64; outputs are native EXEs.
set -euo pipefail
media_dir="${1:-build/media}"
media_dir="$(cd "$media_dir" && pwd)"
x264_source="$(cat "$media_dir/x264-source.txt")"
ffmpeg_source="$(cat "$media_dir/ffmpeg-source.txt")"
if command -v cygpath >/dev/null 2>&1; then
  x264_source="$(cygpath -u "$x264_source")"
  ffmpeg_source="$(cygpath -u "$ffmpeg_source")"
fi
jobs="${REELFORGE_BUILD_JOBS:-4}"
prefix="$media_dir/prefix"
mkdir -p "$prefix" "$media_dir/bin"
cd "$x264_source"
if [ -f config.mak ]; then make distclean; fi
./configure --prefix="$prefix" --enable-static --disable-cli --disable-opencl --disable-asm --enable-pic
make -j"$jobs"
make install
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig"
cd "$ffmpeg_source"
if [ -f ffbuild/config.mak ]; then make distclean; fi
extra_ldflags="-L$prefix/lib"
platform_options=()
case "$(uname -s)" in
  Darwin) platform_options+=(--enable-securetransport) ;;
  MINGW*|MSYS*) platform_options+=(--enable-schannel); extra_ldflags="$extra_ldflags -static" ;;
esac
./configure --prefix="$prefix" --disable-shared --enable-static --disable-autodetect \
  --enable-gpl --enable-libx264 --disable-debug --disable-doc --disable-ffplay \
  --disable-x86asm --extra-cflags="-I$prefix/include" --extra-ldflags="$extra_ldflags" \
  --pkg-config-flags=--static "${platform_options[@]}"
make -j"$jobs"
extension=""
case "$(uname -s)" in MINGW*|MSYS*) extension=".exe" ;; esac
cp "ffmpeg$extension" "ffprobe$extension" "$media_dir/bin/"
cp ffbuild/config.log "$media_dir/notices/ffmpeg-config.log"
cp config.h "$media_dir/notices/ffmpeg-config.h"
echo "Built FFmpeg and ffprobe for $(uname -s)."
