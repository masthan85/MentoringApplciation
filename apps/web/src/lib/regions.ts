"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/browser-api";

export type Region = { code: string; name: string };

// Names for the countries the product knows about; the server decides which are switched on.
const NAMES: Record<string, string> = {
  GB: "United Kingdom",
  IE: "Ireland",
  US: "United States",
  CA: "Canada",
  IN: "India",
};
const FALLBACK: Region[] = ["GB", "IE", "US", "CA"].map((code) => ({ code, name: NAMES[code]! }));

/** The countries a user can choose right now, from the API. */
export function useRegions(): Region[] {
  const [regions, setRegions] = useState<Region[]>(FALLBACK);
  useEffect(() => {
    void (async () => {
      const { data } = await api.GET("/v1/regions");
      if (data) setRegions((data as unknown as Region[]).map((r) => ({ code: r.code, name: r.name })));
    })();
  }, []);
  return regions;
}
