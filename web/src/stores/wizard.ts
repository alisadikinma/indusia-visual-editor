import { defineStore } from "pinia";

import { listBomItems, uploadBom, type BomItem } from "../api/bom";

type State = {
  items: BomItem[];
  loading: boolean;
  uploading: boolean;
  error: string | null;
};

export const useWizardStore = defineStore("wizard", {
  state: (): State => ({
    items: [],
    loading: false,
    uploading: false,
    error: null,
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
    reset() {
      this.items = [];
      this.error = null;
      this.loading = false;
      this.uploading = false;
    },
  },
});
