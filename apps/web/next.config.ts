import type { NextConfig } from "next";

const config: NextConfig = {
  // The Docker image sets NEXT_STANDALONE=1; local `next start` (and the e2e tests) do not use it.
  output: process.env.NEXT_STANDALONE === "1" ? "standalone" : undefined,
  poweredByHeader: false,
};

export default config;
