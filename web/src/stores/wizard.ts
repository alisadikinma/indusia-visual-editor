import { defineStore } from "pinia";

import { listBomItems, uploadBom, type BomItem } from "../api/bom";
import {
  runPreLabel as apiRunPreLabel,
  getPreLabel as apiGetPreLabel,
  type PreLabeledRegion,
} from "../api/prelabel";

type SideState = {
  loading: boolean;
  regions: PreLabeledRegion[];
  error: string | null;
};

type State = {
  items: BomItem[];
  loading: boolean;
  uploading: boolean;
  error: string | null;
  prelabel: { top: SideState; bottom: SideState };
};

const emptySide = (): SideState => ({ loading: false, regions: [], error: null });

export const useWizardStore = defineStore("wizard", {
  state: (): State => ({
    items: [],
    loading: false,
    uploading: false,
    error: null,
    prelabel: { top: emptySide(), bottom: emptySide() },
  }),
  getters: {
    miLikelyCount: (s) => s.items.filter((i) => i.mi_likely).length,
    totalCount: (s) => s.items.length,
  },
  actions: {
    async fetchBomItems(projectId: string) {
      this.loading = true;
      this.error = null;
      try {
        this.items = await listBomItems(projectId);
      } catch (e) {
        this.error = e instanceof Error ? e.message : "Gagal memuat BOM";
      } finally {
        this.loading = false;
      }
    },
    async upload(projectId: string, file: File) {
      this.uploading = true;
      this.error = null;
      try {
        await uploadBom(projectId, file);
        await this.fetchBomItems(projectId);
      } catch (e) {
        this.error = e instanceof Error ? e.message : "Upload gagal";
      } finally {
        this.uploading = false;
      }
    },
    async runPreLabel(projectId: string, side: "top" | "bottom") {
      this.prelabel[side].loading = true;
      this.prelabel[side].error = null;
      try {
        const run = await apiRunPreLabel(projectId, side);
        this.prelabel[side].regions = run.regions;
      } catch (e) {
        this.prelabel[side].error =
          e instanceof Error ? e.message : "Pre-label gagal";
      } finally {
        this.prelabel[side].loading = false;
      }
    },
    async fetchPreLabel(projectId: string, side: "top" | "bottom") {
      this.prelabel[side].loading = true;
      this.prelabel[side].error = null;
      try {
        const run = await apiGetPreLabel(projectId, side);
        this.prelabel[side].regions = run ? run.regions : [];
      } catch (e) {
        this.prelabel[side].error =
          e instanceof Error ? e.message : "Gagal memuat pre-label";
      } finally {
        this.prelabel[side].loading = false;
      }
    },
    reset() {
      this.items = [];
      this.error = null;
      this.loading = false;
      this.uploading = false;
      this.prelabel = { top: emptySide(), bottom: emptySide() };
    },
  },
});
