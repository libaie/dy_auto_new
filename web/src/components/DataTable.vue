<script setup>
import LoadingSpinner from './LoadingSpinner.vue'
import EmptyState from './EmptyState.vue'

const props = defineProps({
  columns: {
    type: Array,
    required: true,
  },
  data: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  total: {
    type: Number,
    default: 0,
  },
  page: {
    type: Number,
    default: 1,
  },
  pageSize: {
    type: Number,
    default: 10,
  },
})

const emit = defineEmits(['page-change'])

const totalPages = () => Math.ceil(props.total / props.pageSize)

const goToPage = (p) => {
  if (p >= 1 && p <= totalPages()) {
    emit('page-change', p)
  }
}
</script>

<template>
  <div class="glass-card overflow-hidden rounded-xl">
    <!-- Loading state -->
    <LoadingSpinner v-if="loading" />

    <!-- Empty state -->
    <EmptyState v-else-if="!data || data.length === 0" />

    <!-- Table -->
    <template v-else>
      <div class="overflow-x-auto">
        <table class="min-w-full">
          <thead>
            <tr>
              <th
                v-for="col in columns"
                :key="col.key"
                scope="col"
                class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider"
                :class="col.headerClass"
              >
                <slot :name="`header-${col.key}`" :col="col">
                  {{ col.label }}
                </slot>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in data" :key="rowIndex" class="hover:bg-white/[0.03] transition-colors">
              <td
                v-for="col in columns"
                :key="col.key"
                class="whitespace-nowrap px-6 py-4 text-sm"
                :class="col.cellClass"
              >
                <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
                  {{ row[col.key] }}
                </slot>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination footer -->
      <div
        v-if="total > pageSize"
        class="flex items-center justify-between border-t border-white/5 px-6 py-3"
      >
        <p class="text-sm text-slate-400">
          共 <span class="font-medium text-slate-300">{{ total }}</span> 条，第
          <span class="font-medium text-slate-300">{{ page }}</span> / {{ totalPages() }} 页
        </p>
        <div class="flex gap-1">
          <button
            :disabled="page <= 1"
            class="rounded-lg border border-white/10 bg-white/5 px-3 py-1 text-sm text-slate-300 hover:bg-white/10 transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
            @click="goToPage(page - 1)"
          >
            上一页
          </button>
          <button
            :disabled="page >= totalPages()"
            class="rounded-lg border border-white/10 bg-white/5 px-3 py-1 text-sm text-slate-300 hover:bg-white/10 transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
            @click="goToPage(page + 1)"
          >
            下一页
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
