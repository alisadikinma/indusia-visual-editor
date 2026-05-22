<script setup lang="ts">
import { computed } from "vue";

import type { BomItem } from "../api/bom";

const props = defineProps<{
  items: BomItem[];
}>();

const totalCount = computed(() => props.items.length);
const miCount = computed(() => props.items.filter((i) => i.mi_likely).length);
const smdCount = computed(
  () => props.items.filter((i) => i.mi_likely === false).length,
);

function miBadgeClass(item: BomItem): string {
  if (item.mi_likely === true) return "bg-warning/20 text-warning";
  if (item.mi_likely === false) return "bg-secondary/20 text-secondary";
  return "bg-bg-deep text-text-tertiary";
}

function miLabel(item: BomItem): string {
  if (item.mi_likely === true) return "MI";
  if (item.mi_likely === false) return "SMT";
  return "?";
}
</script>

<template>
  <div
    class="overflow-hidden rounded-md border border-border-default bg-bg-elevated"
    data-testid="bom-table"
  >
    <div
      v-if="totalCount === 0"
      class="p-8 text-center text-text-secondary"
      data-testid="bom-table-empty"
    >
      Belum ada baris BOM. Upload file Excel atau CSV untuk mulai.
    </div>

    <table v-else class="w-full border-collapse text-sm">
      <thead class="bg-bg-deep">
        <tr class="text-left text-xs uppercase tracking-wide text-text-secondary">
          <th class="px-4 py-3 font-semibold">Designator</th>
          <th class="px-4 py-3 font-semibold">Value</th>
          <th class="px-4 py-3 font-semibold">Package</th>
          <th class="px-4 py-3 font-semibold">Qty</th>
          <th class="px-4 py-3 font-semibold">Tipe</th>
          <th class="px-4 py-3 font-semibold">Komponen</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="item in items"
          :key="item.id"
          class="border-t border-border-default text-text-primary"
          data-testid="bom-row"
        >
          <td class="px-4 py-3 font-mono">{{ item.designator }}</td>
          <td class="px-4 py-3">{{ item.value ?? "—" }}</td>
          <td class="px-4 py-3 font-mono text-text-secondary">
            {{ item.package ?? "—" }}
          </td>
          <td class="px-4 py-3 text-right tabular-nums">{{ item.qty ?? "—" }}</td>
          <td class="px-4 py-3">
            <span
              class="inline-block rounded px-2 py-0.5 text-xs font-semibold"
              :class="miBadgeClass(item)"
            >
              {{ miLabel(item) }}
            </span>
          </td>
          <td class="px-4 py-3 text-text-secondary">
            {{ item.component_type ?? "—" }}
          </td>
        </tr>
      </tbody>
      <tfoot class="bg-bg-deep">
        <tr class="text-xs text-text-secondary">
          <td colspan="6" class="px-4 py-2" data-testid="bom-footer">
            Total <strong>{{ totalCount }}</strong> baris ·
            <strong>{{ miCount }}</strong> MI-likely ·
            <strong>{{ smdCount }}</strong> SMT
          </td>
        </tr>
      </tfoot>
    </table>
  </div>
</template>
