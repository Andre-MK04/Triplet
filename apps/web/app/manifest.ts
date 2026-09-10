import type { MetadataRoute } from "next";

import { BRAND } from "../lib/brand";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: BRAND.name,
    short_name: BRAND.name,
    description: `${BRAND.tagline}.`,
    start_url: "/",
    display: "standalone",
    background_color: "#0b1117",
    theme_color: "#0b1117",
    icons: [
      {
        src: "/farelin-app-icon-7f83cc1f.png",
        sizes: "1000x1000",
        type: "image/png",
      },
    ],
  };
}
