import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Static export: emits web/out (plain HTML/CSS/JS, no Node server) so the
  // Capacitor mobile shell can bundle it directly as its webDir.
  output: "export",
  // next/image's default loader requires the Node image-optimization server,
  // which doesn't exist in a static export — serve images as-is instead.
  images: {
    unoptimized: true,
  },
  // Pin the workspace root to this app dir so Next stops inferring an
  // ancestor directory when multiple lockfiles exist on the machine.
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
