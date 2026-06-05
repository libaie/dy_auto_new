<template>
  <div data-testid="image-workbench-shell" class="min-h-full bg-slate-950 text-slate-100">
    <div class="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <header class="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-bold">图像创作</h1>
          <p class="mt-1 text-sm text-slate-400">内部图像生成工作台，用于创建、跟踪和审查图像资产。</p>
        </div>
        <div class="text-right">
          <button
            type="button"
            data-testid="image-create-submit"
            class="rounded bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="submitting || !canSubmit"
            @click="submit"
          >
            {{ submitting ? '提交中...' : '创建任务' }}
          </button>
          <div
            v-if="selectionPreview?.cost_estimate?.requires_confirmation"
            data-testid="image-submit-confirmation"
            class="mt-3 border border-amber-500/40 bg-amber-950/30 p-3 text-left"
          >
            <p class="text-sm text-amber-100">当前预计成本较高，需要人工确认成本。</p>
            <p v-if="selectionPreview?.cost_estimate?.confirmation_threshold" class="mt-1 text-xs text-amber-200">
              阈值 {{ selectionPreview.cost_estimate.confirmation_threshold }} {{ selectionPreview.cost_estimate.currency || 'CNY' }}
            </p>
            <button
              type="button"
              data-testid="confirm-image-cost"
              class="mt-3 min-h-10 border border-amber-300/70 px-3 py-2 text-xs text-amber-50 hover:bg-amber-900/50"
              @click="costConfirmed = true"
            >
              {{ costConfirmed ? '已确认成本' : '确认成本' }}
            </button>
          </div>
          <p
            v-if="createDisabledReason"
            data-testid="image-create-disabled-reason"
            class="mt-2 max-w-xs text-left text-xs text-amber-200 sm:text-right"
          >
            {{ createDisabledReason }}
          </p>
        </div>
      </header>

      <section data-testid="image-mode-tabs" class="mb-5 border border-slate-800 bg-slate-950/70 p-4">
        <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <button
            v-for="option in modeOptions"
            :key="option.value"
            :data-testid="`mode-${option.value}`"
            type="button"
            class="min-h-12 border px-3 py-2 text-left text-sm transition"
            :class="form.mode === option.value ? 'border-sky-400 bg-sky-950/50 text-sky-100' : 'border-slate-800 bg-slate-900/70 text-slate-300 hover:border-slate-600'"
            @click="setMode(option.value)"
          >
            <span class="block font-medium">{{ option.label }}</span>
            <span class="mt-1 block text-xs text-slate-400">{{ option.hint }}</span>
          </button>
        </div>
      </section>

      <section class="mb-5 border border-slate-800 bg-slate-950/70 p-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="text-base font-semibold">A/B 策略对比</h2>
            <p class="mt-1 text-xs text-slate-400">并行预览多套策略，审查通过后手动选择胜出结果。</p>
          </div>
          <button
            type="button"
            data-testid="ab-mode-toggle"
            class="border border-cyan-500/50 px-3 py-2 text-sm text-cyan-100 hover:bg-cyan-950/50"
            :aria-pressed="String(abModeEnabled)"
            @click="abModeEnabled = !abModeEnabled"
          >
            {{ abModeEnabled ? '收起 A/B' : '启用 A/B' }}
          </button>
        </div>

        <div v-if="abModeEnabled" data-testid="ab-panel" class="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
          <fieldset data-testid="ab-strategy-selector" class="border border-slate-800 bg-slate-950/50 p-3">
            <legend class="px-1 text-sm font-medium text-slate-300">选择策略</legend>
            <div class="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              <label
                v-for="strategy in strategies"
                :key="strategy.id"
                class="flex min-h-10 items-center gap-2 border border-slate-800 bg-slate-900/60 px-3 py-2 text-sm text-slate-200"
              >
                <input
                  v-model="abSelectedStrategyIds"
                  type="checkbox"
                  :value="strategy.id"
                  :data-testid="`ab-strategy-option-${strategy.id}`"
                  class="h-4 w-4 border-slate-700 bg-slate-900"
                />
                <span class="min-w-0 truncate">{{ strategy.name }} v{{ strategy.version }}</span>
              </label>
            </div>
            <p class="mt-2 text-xs text-slate-500">请选择 2-4 个策略。</p>
          </fieldset>

          <div class="space-y-3">
            <div data-testid="ab-status-live" aria-live="polite" class="min-h-16 border border-slate-800 bg-slate-950/50 p-3 text-sm">
              <p v-if="abError" class="text-rose-300">{{ abError }}</p>
              <p v-if="abPreview" class="text-slate-100">{{ abPreviewCostLabel }}</p>
              <p v-if="abCostLimitExceeded" class="mt-1 font-medium text-rose-300">已超出A/B成本上限</p>
              <p v-if="abGroup?.id" class="mt-1 text-xs text-slate-400">对比组：{{ abGroup.id }}</p>
              <p v-if="!abPreview && !abError" class="text-slate-500">先预览成本，再创建对比组。</p>
            </div>

            <div class="grid grid-cols-2 gap-2">
              <button
                type="button"
                data-testid="ab-preview-button"
                class="border border-sky-500/60 px-3 py-2 text-sm text-sky-100 hover:bg-sky-950/50 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="abLoading || !abHasValidStrategyCount"
                @click="previewAbComparison"
              >
                {{ abLoading ? '处理中...' : '预览 A/B' }}
              </button>
              <button
                v-if="abGroup?.id"
                type="button"
                data-testid="ab-refresh-button"
                class="border border-slate-600 px-3 py-2 text-sm text-slate-100 hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="abLoading"
                @click="refreshAbComparison"
              >
                刷新结果
              </button>
              <button
                v-if="abGroup?.id"
                type="button"
                data-testid="ab-load-recommendation"
                class="border border-violet-500/60 px-3 py-2 text-sm text-violet-100 hover:bg-violet-950 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="abRecommendationLoading"
                @click="loadAbWinnerRecommendation"
              >
                {{ abRecommendationLoading ? '处理中...' : '获取推荐' }}
              </button>
            </div>

            <div
              v-if="abWinnerRecommendation || abRecommendationError"
              data-testid="ab-winner-recommendation"
              :role="abRecommendationError ? 'alert' : 'status'"
              :aria-live="abRecommendationError ? undefined : 'polite'"
              class="border border-violet-500/40 bg-violet-950/20 p-3 text-sm text-slate-100"
            >
              <p v-if="abRecommendationError" class="text-rose-300">{{ abRecommendationError }}</p>
              <template v-else>
                <p class="font-mono text-xs text-violet-200">
                  {{ abWinnerRecommendation?.recommended_attempt_id || 'no recommendation' }}
                </p>
                <p class="mt-1 text-xs text-slate-300">{{ abWinnerRecommendation?.reason || 'no recommendation' }}</p>
                <p class="mt-2 text-xs text-amber-200">仍需人工确认</p>
              </template>
            </div>

            <label class="flex items-start gap-2 text-xs text-slate-300">
              <input
                v-model="abCostConfirmed"
                data-testid="ab-cost-confirmation"
                type="checkbox"
                class="mt-0.5 h-4 w-4 border-slate-700 bg-slate-900"
                :disabled="!abPreview || !abCostRequiresConfirmation || abCostLimitExceeded"
              />
              <span>我已确认本次 A/B 会同时创建 {{ abPreview?.strategy_count || abSelectedStrategyIds.length }} 个图像任务。</span>
            </label>

            <div class="grid grid-cols-2 gap-2">
              <button
                type="button"
                data-testid="ab-create-button"
                class="border border-emerald-500/70 px-3 py-2 text-sm text-emerald-100 hover:bg-emerald-950 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="abCreateDisabled"
                @click="createAbComparison"
              >
                创建对比
              </button>
              <button
                v-if="abGroup?.id"
                type="button"
                data-testid="ab-no-winner-button"
                class="border border-amber-500/60 px-3 py-2 text-sm text-amber-100 hover:bg-amber-950 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="abOutcomeDisabled"
                @click="chooseAbNoWinner"
              >
                无胜出方案
              </button>
            </div>
          </div>

          <div v-if="abGroup?.attempts?.length" data-testid="ab-attempt-list" class="lg:col-span-2 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <article
              v-for="attempt in abGroup.attempts"
              :key="attempt.id"
              :data-testid="`ab-attempt-${attempt.id}`"
              class="border border-slate-800 bg-slate-900/60 p-3 text-sm"
            >
              <div class="font-mono text-xs text-slate-500">{{ attempt.id }}</div>
              <div class="mt-1 text-slate-300">{{ attempt.status || 'pending' }}</div>
              <button
                type="button"
                :data-testid="`ab-choose-winner-${attempt.id}`"
                class="mt-3 w-full border border-emerald-500/70 px-3 py-2 text-xs text-emerald-100 hover:bg-emerald-950 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="abOutcomeDisabled || !attempt.approved_asset_ready"
                :aria-label="attempt.approved_asset_ready ? `选择 ${attempt.id} 为胜出方案` : `选择 ${attempt.id} 为胜出方案，需先通过审查`"
                @click="chooseAbWinner(attempt.id)"
              >
                设为胜出
              </button>
              <p v-if="!attempt.approved_asset_ready" class="mt-2 text-xs text-amber-200">需先通过审查</p>
            </article>
          </div>
        </div>
      </section>

      <main class="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section class="space-y-5">
          <div class="border border-slate-800 bg-slate-950/70 p-5">
            <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-300" for="image-prompt">提示词</label>
                <textarea
                  id="image-prompt"
                  v-model="form.prompt"
                  data-testid="image-prompt"
                  rows="8"
                  class="w-full resize-y border border-slate-700 bg-slate-900 px-3 py-3 text-sm text-slate-100 outline-none focus:border-sky-500"
                  placeholder="描述画面主体、风格、构图、光线和需要避免的问题"
                />
              </div>
              <div class="grid content-start gap-4">
                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-300" for="destination-role">目标用途</label>
                  <select
                    id="destination-role"
                    v-model="form.destination_role"
                    data-testid="destination-role"
                    class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                  >
                    <option value="">不指定</option>
                    <option value="character_anchor">角色锚定图</option>
                    <option value="scene_reference">场景参考图</option>
                    <option value="style_reference">风格参考图</option>
                    <option value="storyboard_frame">分镜画面</option>
                    <option value="image_to_video_input">图生视频输入</option>
                  </select>
                </div>
                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-300" for="strategy-select">生产策略</label>
                  <select
                    id="strategy-select"
                    v-model="selectedStrategyId"
                    data-testid="strategy-select"
                    class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                  >
                    <option value="">自动策略</option>
                    <option v-for="strategy in strategies" :key="strategy.id" :value="strategy.id">
                      {{ strategy.name }} v{{ strategy.version }}
                    </option>
                  </select>
                </div>
                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-300" for="image-count">生成数量</label>
                  <input
                    id="image-count"
                    v-model.number="form.count"
                    data-testid="image-count"
                    type="number"
                    min="1"
                    max="8"
                    class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                  />
                  <p v-if="countError" class="mt-2 text-sm text-rose-300">{{ countError }}</p>
                </div>
              </div>
            </div>
          </div>

          <div data-testid="image-model-params" class="border border-slate-800 bg-slate-950/70 p-5">
            <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h2 class="text-base font-semibold">模型与参数</h2>
              <span class="text-xs text-slate-500">{{ selectedModel ? `${selectedModel.provider} / ${selectedModel.model_name || selectedModel.name}` : '未指定模型时由后端自动选择' }}</span>
            </div>
            <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-300" for="image-model-select">图像模型</label>
                <select
                  id="image-model-select"
                  v-model="form.modelId"
                  data-testid="image-model-select"
                  class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                  @change="pruneProviderOptions"
                >
                  <option value="">后端自动选择</option>
                  <option v-for="model in imageModels" :key="model.id" :value="model.id">
                    {{ model.name }}
                  </option>
                </select>
              </div>
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-300" for="image-size">尺寸</label>
                <input
                  id="image-size"
                  v-model.trim="form.size"
                  data-testid="image-size"
                  class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                  placeholder="3K / 1024x1024"
                />
              </div>
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-300" for="image-output-format">输出格式</label>
                <select
                  id="image-output-format"
                  v-model="form.output_format"
                  data-testid="image-output-format"
                  class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                >
                  <option value="">跟随模型</option>
                  <option v-for="option in outputFormatOptions" :key="option" :value="option">{{ option.toUpperCase() }}</option>
                </select>
              </div>
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-300" for="image-response-format">响应格式</label>
                <select
                  id="image-response-format"
                  v-model="form.response_format"
                  data-testid="image-response-format"
                  class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                >
                  <option value="">跟随模型</option>
                  <option v-for="option in responseFormatOptions" :key="option" :value="option">{{ option === 'url' ? 'URL' : 'Base64 JSON' }}</option>
                </select>
              </div>
              <label class="flex items-center gap-2 text-sm text-slate-300">
                <input
                  v-model="form.watermark"
                  data-testid="image-watermark"
                  type="checkbox"
                  class="h-4 w-4 border-slate-700 bg-slate-900"
                />
                添加水印
              </label>
            </div>

            <div v-if="providerOptionFields.length" class="mt-5 border-t border-slate-800 pt-4">
              <h3 class="mb-3 text-sm font-medium text-slate-300">模型专属参数</h3>
              <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <div v-for="field in providerOptionFields" :key="field.key">
                  <label class="mb-2 block text-sm font-medium text-slate-300" :for="`provider-option-${field.key}`">
                    {{ providerOptionLabel(field.key) }}
                  </label>
                  <select
                    v-if="field.type === 'select'"
                    :id="`provider-option-${field.key}`"
                    v-model="form.providerOptions[field.key]"
                    :data-testid="`provider-option-${field.key}`"
                    class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                  >
                    <option value="">跟随模型</option>
                    <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
                  </select>
                  <label v-else-if="field.type === 'boolean'" class="flex min-h-10 items-center gap-2 border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-300">
                    <input
                      v-model="form.providerOptions[field.key]"
                      :data-testid="`provider-option-${field.key}`"
                      type="checkbox"
                      class="h-4 w-4 border-slate-700 bg-slate-900"
                    />
                    开启
                  </label>
                  <input
                    v-else-if="field.type === 'number'"
                    :id="`provider-option-${field.key}`"
                    v-model.number="form.providerOptions[field.key]"
                    :data-testid="`provider-option-${field.key}`"
                    type="number"
                    :min="field.min"
                    :max="field.max"
                    class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                  />
                  <input
                    v-else
                    :id="`provider-option-${field.key}`"
                    v-model.trim="form.providerOptions[field.key]"
                    :data-testid="`provider-option-${field.key}`"
                    type="text"
                    class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                  />
                </div>
              </div>
            </div>
          </div>

          <div data-testid="image-reference-board" class="border border-slate-800 bg-slate-950/70 p-5">
            <h2 class="mb-4 text-base font-semibold">源图与参考图</h2>
            <div class="grid gap-4 lg:grid-cols-2">
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-300" for="source-file">上传源图</label>
                <input
                  id="source-file"
                  data-testid="source-file"
                  type="file"
                  accept="image/*"
                  class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 file:mr-3 file:border-0 file:bg-slate-700 file:px-3 file:py-1 file:text-slate-100"
                  @change="uploadSource"
                />
                <p v-if="uploading" class="mt-2 text-sm text-slate-400">上传中...</p>
              </div>
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-300" for="source-url">源图 URL</label>
                <input
                  id="source-url"
                  v-model.trim="form.sourceUrl"
                  data-testid="source-url"
                  class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                  placeholder="https://example.com/source.png"
                  @input="form.sourceAssetId = ''"
                />
                <p v-if="sourceError" class="mt-2 text-sm text-rose-300">{{ sourceError }}</p>
              </div>
              <div class="lg:col-span-2">
                <label class="mb-2 block text-sm font-medium text-slate-300" for="reference-urls">参考图 URL</label>
                <textarea
                  id="reference-urls"
                  v-model="form.referenceUrls"
                  data-testid="reference-urls"
                  rows="4"
                  class="w-full resize-y border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                  placeholder="每行填写一个参考图 URL"
                />
                <p v-if="referenceError" class="mt-2 text-sm text-rose-300">{{ referenceError }}</p>
              </div>
            </div>

            <div class="mt-5 border-t border-slate-800 pt-4">
              <div class="mb-3 flex items-center justify-between gap-3">
                <h3 class="text-sm font-medium text-slate-300">已批准资产</h3>
                <button
                  type="button"
                  class="border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-slate-500"
                  @click="loadApprovedAssets"
                >
                  刷新列表
                </button>
              </div>
              <div v-if="approvedAssets.length" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <div
                  v-for="asset in approvedAssets"
                  :key="asset.id"
                  class="border border-slate-800 bg-slate-900/60 p-3"
                >
                  <img
                    v-if="assetUrl(asset)"
                    :src="assetUrl(asset)"
                    :alt="asset.prompt || '已批准资产'"
                    class="aspect-video w-full object-cover"
                  />
                  <div class="mt-2 line-clamp-2 text-sm text-slate-300">{{ asset.prompt || '已批准图像资产' }}</div>
                  <div class="mt-3 grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      :data-testid="`use-approved-asset-${asset.id}`"
                      class="border border-sky-500/70 px-3 py-1 text-xs text-sky-100 hover:bg-sky-950"
                      @click="useApprovedAsset(asset)"
                    >
                      设为源图
                    </button>
                    <button
                      type="button"
                      :data-testid="`toggle-reference-asset-${asset.id}`"
                      class="border px-3 py-1 text-xs hover:bg-emerald-950"
                      :class="isReferenceAssetSelected(asset) ? 'border-emerald-400 text-emerald-100' : 'border-slate-700 text-slate-200'"
                      @click="toggleReferenceAsset(asset)"
                    >
                      {{ isReferenceAssetSelected(asset) ? '已作参考' : '作参考图' }}
                    </button>
                  </div>
                </div>
              </div>
              <p v-else class="text-sm text-slate-500">暂无已批准资产。</p>
            </div>
          </div>

          <p v-if="error" class="border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">{{ error }}</p>
        </section>

        <aside class="space-y-5">
        <section data-testid="image-trust-rail" class="border border-slate-800 bg-slate-950/70 p-5" aria-live="polite">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-base font-semibold">生产信任检查</h2>
            <button
              type="button"
              data-testid="selection-preview-button"
              class="border border-sky-500/40 px-3 py-2 text-sm text-sky-200 hover:bg-sky-950/50 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="previewLoading || !form.mode"
              @click="runSelectionPreview"
            >
              {{ previewLoading ? '预览中...' : '选择预览' }}
            </button>
          </div>
          <p v-if="previewError" class="mt-3 text-sm text-rose-300">{{ previewError }}</p>
          <div v-if="selectionPreview" class="mt-4 space-y-3 text-sm">
            <div class="grid gap-3">
              <section class="border border-slate-800 bg-slate-950/50 p-3">
                <p class="text-xs font-semibold text-slate-300">提交前检查</p>
                <dl class="mt-3 grid gap-2 text-xs">
                  <div class="flex items-center justify-between gap-3">
                    <dt class="text-slate-500">预览状态</dt>
                    <dd class="text-slate-100">{{ previewStatusLabel }}</dd>
                  </div>
                  <div class="flex items-center justify-between gap-3">
                    <dt class="text-slate-500">预计成本</dt>
                    <dd class="text-slate-100">{{ previewCostLabel }}</dd>
                  </div>
                  <div class="flex items-center justify-between gap-3">
                    <dt class="text-slate-500">预计耗时</dt>
                    <dd class="text-slate-100">{{ timeEstimateLabel }}</dd>
                  </div>
                  <div class="flex items-center justify-between gap-3">
                    <dt class="text-slate-500">产能</dt>
                    <dd class="text-slate-100">{{ capacityStatusLabel }}</dd>
                  </div>
                  <div v-if="previewCostRequiresConfirmation" class="flex items-center justify-between gap-3">
                    <dt class="text-slate-500">成本确认</dt>
                    <dd class="text-amber-100">{{ highCostConfirmationLabel }}</dd>
                  </div>
                </dl>
                <p v-if="previewCapacity.estimated_wait_seconds" class="mt-2 text-xs text-slate-400">
                  预计等待 {{ previewCapacity.estimated_wait_seconds }} 秒
                </p>
              </section>

              <section class="border border-slate-800 bg-slate-950/50 p-3">
                <p class="text-xs font-semibold text-slate-300">生产路径</p>
                <p class="mt-2 text-xs text-slate-400">{{ previewSelectedModelPathLabel }}</p>
                <p class="mt-1 text-xs text-slate-400">{{ previewStrategyPathLabel }}</p>
                <p v-if="previewCapacity.queue_depth !== undefined" class="mt-1 text-xs text-slate-400">
                  队列深度 {{ previewCapacity.queue_depth || 0 }}
                </p>
              </section>

              <section class="border border-slate-800 bg-slate-950/50 p-3">
                <p class="text-xs font-semibold text-slate-300">审查门禁</p>
                <p class="mt-2 text-xs text-slate-100">{{ reviewGateLabel }}</p>
                <p v-if="previewReviewGate.required || previewReviewGate.manual_required || previewReviewGate.ai_required" class="mt-1 text-xs text-slate-400">
                  生成后必须通过对应审查，才能推广到视频生产。
                </p>
              </section>
            </div>

            <div v-if="primaryFallbackAction" class="border border-amber-500/40 bg-amber-950/30 p-3">
              <p class="text-amber-100">当前预览需要先确认 fallback 模型后才能创建任务。</p>
              <p v-if="fallbackCandidates.length" class="mt-1 text-xs text-amber-200">
                可用 fallback：{{ fallbackCandidateSummary }}
              </p>
              <button
                type="button"
                :data-testid="`confirm-fallback-model-${primaryFallbackAction.model_id}`"
                class="mt-3 border border-amber-300/70 px-3 py-1 text-xs text-amber-50 hover:bg-amber-900/50 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="previewLoading"
                @click="handleRescueAction(primaryFallbackAction)"
              >
                使用 fallback 模型
              </button>
            </div>

            <details v-if="rejectedCandidates.length || fallbackCandidates.length || rescueActions.length" class="border-t border-slate-800 pt-3">
              <summary class="cursor-pointer text-slate-300">候选诊断</summary>
              <div v-if="rejectedCandidates.length" class="mt-3">
                <p class="text-slate-400">已拒绝候选模型</p>
                <ul class="mt-2 space-y-2">
                  <li
                    v-for="candidate in rejectedCandidates"
                    :key="candidate.model_id || candidate.id || candidate.name"
                    class="border border-slate-800 bg-slate-900/60 p-3"
                  >
                    <p class="font-medium text-slate-100">{{ candidate.name || candidate.model_id || candidate.id }}</p>
                    <p v-if="candidate.reason" class="mt-1 text-xs text-amber-200">{{ rejectedReasonLabel(candidate.reason) }}</p>
                    <p class="mt-1 text-xs text-slate-400">{{ rejectedDetailLabel(candidate) }}</p>
                    <p v-if="candidate.rescue_action" class="mt-1 text-xs text-sky-200">{{ rejectedRescueLabel(candidate) }}</p>
                  </li>
                </ul>
              </div>
              <div v-if="fallbackCandidates.length" class="mt-3">
                <p class="text-slate-400">fallback 候选模型</p>
                <ul class="mt-2 space-y-2">
                  <li
                    v-for="candidate in fallbackCandidates"
                    :key="candidate.model_id || candidate.id || candidate.name"
                    class="border border-slate-800 bg-slate-900/60 p-3"
                  >
                    <p class="font-medium text-slate-100">{{ candidate.name || candidate.model_id || candidate.id }}</p>
                    <p class="mt-1 text-xs text-slate-400">{{ fallbackCandidateLabel(candidate) }}</p>
                  </li>
                </ul>
              </div>
            </details>
            <details class="border-t border-slate-800 pt-3">
              <summary class="cursor-pointer text-slate-300">审计详情</summary>
              <pre class="mt-3 max-h-64 overflow-auto bg-slate-900 p-3 text-xs text-slate-300">{{ JSON.stringify(selectionPreview.selection_explanation, null, 2) }}</pre>
            </details>
          </div>
          <p v-else class="mt-4 text-sm text-slate-500">提交前运行选择预览，确认模型、成本和审查门禁。</p>
        </section>

        <section data-testid="image-task-panel" class="border border-slate-800 bg-slate-950/70 p-5">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-base font-semibold">任务与结果</h2>
            <div class="flex gap-2">
              <button
                type="button"
                data-testid="refresh-image-task"
                class="border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="!task?.id || syncing"
                @click="refreshTask"
              >
                刷新
              </button>
              <button
                type="button"
                data-testid="sync-image-task"
                class="border border-sky-500/70 px-3 py-1 text-xs text-sky-100 hover:bg-sky-950 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="!task?.id || syncing"
                @click="syncTask"
              >
                同步
              </button>
              <button
                v-if="task?.queue_job_id && !task?.pixelle_task_id"
                type="button"
                data-testid="dispatch-queued-image-task"
                class="border border-amber-500/70 px-3 py-1 text-xs text-amber-100 hover:bg-amber-950 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="syncing"
                @click="dispatchQueuedTask"
              >
                手动调度排队任务
              </button>
            </div>
          </div>
          <div data-testid="task-results-live" class="mt-4 space-y-4" aria-live="polite">
            <div class="border border-slate-800 bg-slate-900/60 p-3">
              <div class="text-xs text-slate-500">当前任务状态</div>
              <div class="mt-1 font-mono text-sm text-slate-100">{{ currentStatus }}</div>
              <div v-if="task?.id" class="mt-1 break-all font-mono text-xs text-slate-500">{{ task.id }}</div>
              <div v-if="task?.pixelle_task_id" class="mt-1 break-all font-mono text-xs text-slate-500">{{ task.pixelle_task_id }}</div>
            </div>

            <div
              v-if="task?.queue_job_id && !task?.pixelle_task_id"
              data-testid="image-queue-status"
              class="border border-amber-500/40 bg-amber-950/20 p-3 text-xs text-amber-100"
            >
              {{ queueStatusLabel }}
              <p class="mt-1 text-amber-200/80">该任务尚未提交到 Pixelle，手动调度后才会进入真实生成。</p>
            </div>

            <div
              v-if="taskTimeline.length"
              data-testid="image-production-timeline"
              class="border border-slate-800 bg-slate-900/60 p-3"
            >
              <div class="text-xs text-slate-500">生产步骤</div>
              <ol role="list" class="mt-3 space-y-3">
                <li
                  v-for="step in taskTimeline"
                  :key="step.key || step.label"
                  :data-testid="`image-production-timeline-step-${step.key}`"
                  :aria-current="isCurrentTimelineStep(step) ? 'step' : undefined"
                  class="flex gap-3"
                >
                  <span class="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" :class="timelineDotClass(step.status)" />
                  <span class="min-w-0">
                    <span class="block text-sm text-slate-100">{{ timelineStepLabel(step) }}</span>
                    <span class="mt-1 block text-xs" :class="timelineStatusClass(step.status)">
                      {{ timelineStatusLabel(step.status) }}
                    </span>
                  </span>
                </li>
              </ol>
            </div>

            <div
              v-if="taskRescueActions.length"
              data-testid="image-task-rescue-actions"
              class="border border-amber-500/40 bg-amber-950/30 p-3"
            >
              <div class="text-xs font-semibold text-amber-100">可执行修复</div>
              <p v-if="taskFallbackTrace.message" class="mt-2 text-xs text-amber-100/80">{{ taskFallbackTrace.message }}</p>
              <div class="mt-3 flex flex-wrap gap-2">
                <button
                  v-for="action in taskRescueActions"
                  :key="`${action.type}-${action.model_id || action.label}`"
                  type="button"
                  :data-testid="`retry-fallback-model-${action.model_id}`"
                  class="border border-amber-300/60 px-3 py-2 text-xs font-semibold text-amber-50 hover:bg-amber-900/50"
                  @click="handleTaskRescueAction(action)"
                >
                  {{ taskRescueActionLabel(action) }}
                </button>
              </div>
            </div>

            <div v-if="assets.length" data-testid="image-review-backlog-filter" class="flex flex-wrap gap-2">
              <button
                type="button"
                data-testid="review-filter-needs_review"
                :aria-pressed="reviewAssetFilter === 'needs_review'"
                :class="reviewAssetFilter === 'needs_review' ? activeFilterClass : idleFilterClass"
                @click="reviewAssetFilter = 'needs_review'"
              >
                待审 {{ assetReviewCounts.needs_review }}
              </button>
              <button
                type="button"
                data-testid="review-filter-approved"
                :aria-pressed="reviewAssetFilter === 'approved'"
                :class="reviewAssetFilter === 'approved' ? activeFilterClass : idleFilterClass"
                @click="reviewAssetFilter = 'approved'"
              >
                已通过 {{ assetReviewCounts.approved }}
              </button>
              <button
                type="button"
                data-testid="review-filter-blocked"
                :aria-pressed="reviewAssetFilter === 'blocked'"
                :class="reviewAssetFilter === 'blocked' ? activeFilterClass : idleFilterClass"
                @click="reviewAssetFilter = 'blocked'"
              >
                阻断/驳回 {{ assetReviewCounts.blocked }}
              </button>
              <button
                type="button"
                data-testid="review-filter-all"
                :aria-pressed="reviewAssetFilter === 'all'"
                :class="reviewAssetFilter === 'all' ? activeFilterClass : idleFilterClass"
                @click="reviewAssetFilter = 'all'"
              >
                全部 {{ assetReviewCounts.all }}
              </button>
            </div>

            <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <div
                v-for="asset in filteredAssets"
                :key="asset.id || asset.url || asset.image_url"
                class="overflow-hidden border border-slate-800 bg-slate-900/60"
              >
                <img
                  v-if="assetUrl(asset)"
                  :src="assetUrl(asset)"
                  :alt="asset.prompt || '生成结果'"
                  class="aspect-square w-full object-cover"
                />
                <div v-else class="flex aspect-square items-center justify-center bg-slate-900 text-sm text-slate-500">
                  暂无预览
                </div>
                <div class="p-3 text-sm">
                  <div class="font-mono text-xs text-slate-500">{{ asset.status || '待处理' }}</div>
                  <div class="mt-1 line-clamp-2 text-slate-300">{{ asset.prompt || form.prompt || '图像资产' }}</div>
                  <p v-if="asset.review_gate?.status" class="mt-2 text-xs text-slate-400">
                    审查状态：{{ assetReviewGateLabel(asset.review_gate) }}
                  </p>
                  <div v-if="asset.id" class="mt-3 grid grid-cols-2 gap-2">
                    <button
                      v-if="assetAllowed(asset, 'approve')"
                      type="button"
                      :data-testid="`approve-asset-${asset.id}`"
                      class="border border-emerald-500/70 px-2 py-1 text-xs text-emerald-100 hover:bg-emerald-950"
                      @click="reviewAsset(asset, 'approve')"
                    >
                      通过
                    </button>
                    <button
                      v-if="assetAllowed(asset, 'reject')"
                      type="button"
                      :data-testid="`reject-asset-${asset.id}`"
                      class="border border-rose-500/70 px-2 py-1 text-xs text-rose-100 hover:bg-rose-950"
                      @click="reviewAsset(asset, 'reject')"
                    >
                      拒绝
                    </button>
                    <button
                      v-if="assetAllowed(asset, 'repaint')"
                      type="button"
                      :data-testid="`edit-asset-${asset.id}`"
                      class="border border-sky-500/70 px-2 py-1 text-xs text-sky-100 hover:bg-sky-950"
                      @click="editAgain(asset)"
                    >
                      重绘
                    </button>
                    <button
                      v-if="assetAllowed(asset, 'copy_as_new_task')"
                      type="button"
                      :data-testid="`copy-asset-${asset.id}`"
                      class="border border-slate-600 px-2 py-1 text-xs text-slate-100 hover:bg-slate-800"
                      @click="copyAsNewTask(asset)"
                    >
                      复制为新任务
                    </button>
                    <button
                      v-if="canPromoteAsset(asset)"
                      type="button"
                      :data-testid="`promote-asset-${asset.id}`"
                      class="border border-violet-500/70 px-2 py-1 text-xs text-violet-100 hover:bg-violet-950"
                      @click="promoteAsset(asset)"
                    >
                      推广到视频
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div
              v-if="assets.length && filteredAssets.length === 0"
              data-testid="image-review-empty-state"
              class="py-10 text-center text-sm text-slate-500"
            >
              当前没有{{ reviewAssetFilterLabel }}资产。
            </div>

            <div v-if="assets.length === 0" class="py-10 text-center text-sm text-slate-500">
              提交任务后，生成结果会显示在这里。
            </div>
          </div>
        </section>
        </aside>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import {
  createImageTask,
  dispatchQueuedImageTask,
  editImageAsset,
  getImageTask,
  listImageAssets,
  reviewImageAsset,
  syncImageTask,
  uploadImageSource,
} from '../api/imageCreation.js'
import { listModels } from '../api/aiConfig.js'
import {
  chooseImageAbNoWinner,
  chooseImageAbWinner,
  createImageAbTest,
  getImageAbWinnerRecommendation,
  listImageProductionStrategies,
  previewImageSelection,
  previewImageAbTest,
  promoteImageAssetToVideo,
  refreshImageAbTest,
} from '../api/imageProduction.js'

const modeOptions = [
  { value: 'text_to_image', label: '文生图', hint: '仅使用提示词生成' },
  { value: 'image_to_image', label: '以图改图', hint: '基于源图重绘' },
  { value: 'multi_reference_to_image', label: '多图参考', hint: '融合多张参考图' },
  { value: 'text_to_image_set', label: '文生组图', hint: '提示词生成一组图' },
  { value: 'image_to_image_set', label: '一图组图', hint: '源图扩展为组图' },
  { value: 'multi_reference_to_image_set', label: '多参考组图', hint: '按参考生成一组图' },
]

const form = reactive({
  mode: 'text_to_image',
  prompt: '',
  destination_role: 'image_to_video_input',
  count: 1,
  sourceUrl: '',
  sourceAssetId: '',
  referenceUrls: '',
  referenceAssetIds: [],
  modelId: '',
  size: '',
  output_format: '',
  response_format: '',
  watermark: false,
  providerOptions: {},
})

const submitting = ref(false)
const uploading = ref(false)
const syncing = ref(false)
const error = ref('')
const task = ref(null)
const assets = ref([])
const approvedAssets = ref([])
const imageModels = ref([])
const strategies = ref([])
const selectedStrategyId = ref('')
const selectionPreview = ref(null)
const selectionPreviewRequestToken = ref(0)
const previewLoading = ref(false)
const previewError = ref('')
const costConfirmed = ref(false)
const requiresFreshPreviewAfterHighCost = ref(false)
const reviewAssetFilter = ref('needs_review')
const abModeEnabled = ref(false)
const abSelectedStrategyIds = ref([])
const abPreview = ref(null)
const abGroup = ref(null)
const abLoading = ref(false)
const abError = ref('')
const abWinnerRecommendation = ref(null)
const abRecommendationLoading = ref(false)
const abRecommendationError = ref('')
const abRecommendationRequestToken = ref(0)
const abCostConfirmed = ref(false)
const abRequestToken = ref(0)
const abCreateIdempotencyKey = ref('')
const abCreateRequestHash = ref('')
const abTerminalStatuses = new Set(['winner_selected', 'no_winner', 'cancelled', 'failed'])
const abDecisionReadyStatuses = new Set(['completed', 'partial_failed'])

const requiresSource = computed(() => modeAcceptsSource(form.mode))
const requiresReferences = computed(() => modeAcceptsReferences(form.mode))
const referenceImages = computed(() => {
  const urlReferences = form.referenceUrls
    .split(/\r?\n/)
    .map(url => url.trim())
    .filter(Boolean)
    .map(url => ({ url }))
  const assetReferences = form.referenceAssetIds
    .map(assetId => approvedAssets.value.find(asset => asset.id === assetId))
    .filter(Boolean)
    .map(asset => ({ asset_id: asset.id, url: assetUrl(asset) }))
  return [...urlReferences, ...assetReferences]
})
const sourceError = computed(() => requiresSource.value && !form.sourceUrl.trim() && !form.sourceAssetId ? '请填写源图 URL 或上传源图' : '')
const referenceError = computed(() => requiresReferences.value && referenceImages.value.length < 2 ? '请至少填写两张参考图 URL' : '')
const countError = computed(() => !form.mode.endsWith('_set') && Number(form.count) > 1 ? '单张模式的生成数量只能为 1' : '')
const previewBlocked = computed(() => Boolean(
  selectionPreview.value?.preview_blocked
    || selectionPreview.value?.error_code === 'IMAGE_FALLBACK_REQUIRES_CONFIRMATION',
))
const previewCapacity = computed(() => selectionPreview.value?.capacity || {})
const previewReviewGate = computed(() => selectionPreview.value?.review_gate || {})
const previewTimeEstimate = computed(() => selectionPreview.value?.time_estimate || {})
const previewCostRequiresConfirmation = computed(() => Boolean(selectionPreview.value?.cost_estimate?.requires_confirmation))
const costConfirmationRequired = computed(() => Boolean(
  (previewCostRequiresConfirmation.value && !costConfirmed.value) || requiresFreshPreviewAfterHighCost.value,
))
const canSubmit = computed(() => Boolean(form.prompt.trim())
  && !sourceError.value
  && !referenceError.value
  && !countError.value
  && !previewBlocked.value
  && !costConfirmationRequired.value)
const createDisabledReason = computed(() => {
  if (!form.prompt.trim()) return '请先填写提示词。'
  if (sourceError.value) return sourceError.value
  if (referenceError.value) return referenceError.value
  if (countError.value) return countError.value
  if (previewBlocked.value) return '当前预览需要先确认 fallback 模型后才能创建任务。'
  if (requiresFreshPreviewAfterHighCost.value) return '请求已变化，请重新运行选择预览后确认成本。'
  if (costConfirmationRequired.value) return '当前预计成本较高，需要先确认成本后才能创建任务。'
  return ''
})
const abCostEstimate = computed(() => abPreview.value?.total_cost_estimate || abPreview.value?.cost_estimate || {})
const abCostRequiresConfirmation = computed(() => Boolean(abCostEstimate.value.requires_confirmation))
const abCostLimitExceeded = computed(() => Boolean(abCostEstimate.value.cost_limit_exceeded || abPreview.value?.cost_limit_exceeded))
const abHasValidStrategyCount = computed(() => abSelectedStrategyIds.value.length >= 2 && abSelectedStrategyIds.value.length <= 4)
const abPreviewCostLabel = computed(() => {
  const estimate = abCostEstimate.value
  if (!estimate || estimate.amount === undefined || estimate.amount === null) return '暂无成本预估'
  return `${estimate.amount} ${estimate.currency || 'CNY'}`
})
const abCreateDisabled = computed(() => Boolean(
  abLoading.value
    || abGroup.value?.id
    || !abPreview.value?.request_hash
    || !abHasValidStrategyCount.value
    || !form.prompt.trim()
    || sourceError.value
    || referenceError.value
    || countError.value
    || abCostLimitExceeded.value
    || (abCostRequiresConfirmation.value && !abCostConfirmed.value),
))
const abGroupTerminal = computed(() => abTerminalStatuses.has(abGroup.value?.status))
const abOutcomeReady = computed(() => Boolean(
  abGroup.value?.id
    && !abGroupTerminal.value
    && abDecisionReadyStatuses.has(abGroup.value?.status),
))
const abOutcomeDisabled = computed(() => abLoading.value || !abOutcomeReady.value)
const currentStatus = computed(() => taskStatusLabel(task.value?.status))
const selectedModel = computed(() => imageModels.value.find(model => model.id === form.modelId) || null)
const providerOptionSchema = computed(() => selectedModel.value?.config_json?.provider_options_schema || {})
const outputFormatOptions = computed(() => schemaOptions('output_format', ['jpeg', 'png']))
const responseFormatOptions = computed(() => schemaOptions('response_format', ['url', 'b64_json']))
const providerOptionFields = computed(() => Object.entries(providerOptionSchema.value)
  .filter(([key]) => !['watermark', 'response_format', 'output_format'].includes(key))
  .map(([key, schema]) => ({ key, ...(schema || {}) })))
const selectedStrategy = computed(() => strategies.value.find(strategy => strategy.id === selectedStrategyId.value) || null)
const rejectedCandidates = computed(() => selectionPreview.value?.selection_explanation?.rejected_candidates || [])
const fallbackCandidates = computed(() => selectionPreview.value?.fallback_candidates || [])
const rescueActions = computed(() => selectionPreview.value?.rescue_actions || [])
const taskTimeline = computed(() => Array.isArray(task.value?.timeline) ? task.value.timeline : [])
const taskFallbackTrace = computed(() => task.value?.fallback_trace || {})
const taskRescueActions = computed(() => Array.isArray(taskFallbackTrace.value?.rescue_actions) ? taskFallbackTrace.value.rescue_actions : [])
const primaryFallbackAction = computed(() => rescueActions.value.find(action => action.type === 'confirm_fallback_model' && action.model_id) || null)
const fallbackCandidateSummary = computed(() => fallbackCandidates.value
  .map(candidate => candidate.name || candidate.model_id || candidate.id)
  .filter(Boolean)
  .join('、'))
const previewStatusLabel = computed(() => {
  if (previewBlocked.value) return '需确认 fallback'
  if (selectionPreview.value?.ok === false) return '预览失败'
  return '可提交'
})
const previewSelectedModelLabel = computed(() => selectionPreview.value?.selected_model?.name
  || selectionPreview.value?.selected_model?.model_id
  || '后端自动选择')
const previewCostLabel = computed(() => {
  const estimate = selectionPreview.value?.cost_estimate
  if (!estimate || estimate.amount === undefined || estimate.amount === null) return '-'
  return `${estimate.amount} ${estimate.currency || ''}`.trim()
})
const previewStrategyLabel = computed(() => selectedStrategy.value ? `策略 v${selectedStrategy.value.version}` : '自动策略')
const previewSelectedModelPathLabel = computed(() => selectionPreview.value?.selected_model?.name
  || selectionPreview.value?.selected_model?.model_id
  || '尚未选择模型')
const previewStrategyPathLabel = computed(() => {
  const strategy = selectionPreview.value?.strategy || selectedStrategy.value
  if (!strategy) return previewStrategyLabel.value
  return `${strategy.name || '图像策略'} v${strategy.version || 1}`
})
const timeEstimateLabel = computed(() => {
  const seconds = previewTimeEstimate.value.estimated_seconds
  return seconds ? `预计 ${seconds} 秒` : '-'
})
const capacityStatusLabel = computed(() => {
  if (previewCapacity.value.status === 'queued') return `将进入队列，前方 ${previewCapacity.value.queue_depth || 0} 个任务`
  if (previewCapacity.value.status === 'blocked') return '当前产能已满'
  return '可立即提交'
})
const reviewGateLabel = computed(() => {
  if (previewReviewGate.value.manual_required) return '需要人工审查'
  if (previewReviewGate.value.ai_required) return '需要 AI 审查'
  return '无需额外审查'
})
const highCostConfirmationLabel = computed(() => {
  if (costConfirmed.value) return '已确认成本'
  return '需要人工确认成本'
})
const activeFilterClass = 'border border-cyan-400 bg-cyan-950/40 px-3 py-1 text-xs text-cyan-50'
const idleFilterClass = 'border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-900'
const assetReviewCounts = computed(() => ({
  needs_review: assets.value.filter(asset => ['review_pending', 'manual_review_pending'].includes(asset.status)).length,
  approved: assets.value.filter(asset => asset.status === 'approved').length,
  blocked: assets.value.filter(asset => ['blocked', 'rejected'].includes(asset.status)).length,
  all: assets.value.length,
}))
const filteredAssets = computed(() => {
  if (reviewAssetFilter.value === 'all') return assets.value
  if (reviewAssetFilter.value === 'approved') return assets.value.filter(asset => asset.status === 'approved')
  if (reviewAssetFilter.value === 'blocked') return assets.value.filter(asset => ['blocked', 'rejected'].includes(asset.status))
  return assets.value.filter(asset => ['review_pending', 'manual_review_pending'].includes(asset.status))
})
const reviewAssetFilterLabel = computed(() => {
  if (reviewAssetFilter.value === 'approved') return '已通过'
  if (reviewAssetFilter.value === 'blocked') return '阻断或驳回'
  if (reviewAssetFilter.value === 'all') return ''
  return '待审'
})
const queueStatusLabel = computed(() => {
  const capacity = task.value?.capacity || {}
  if (task.value?.status !== 'queued') return ''
  return `排队中，前方 ${capacity.queue_depth || 0} 个任务，预计等待 ${capacity.estimated_wait_seconds || 0} 秒`
})

const timelineStatusLabels = {
  pending: '待处理',
  queued: '排队中',
  running: '运行中',
  completed: '已完成',
  blocked: '已阻断',
  failed: '失败',
  skipped: '已跳过',
}

const timelineStepLabels = {
  preview: '选择预览',
  snapshot: '任务快照',
  queue: '进入队列',
  generation: '图像生成',
  review: '审查门禁',
  approval: '人工确认',
}

const taskStatusLabels = {
  pending: '待处理',
  queued: '排队中',
  running: '生成中',
  completed: '已完成',
  blocked: '已阻断',
  failed: '失败',
  skipped: '已跳过',
}

const rejectedReasonLabels = {
  disabled: '模型已停用',
  model_disabled: '模型已停用',
  not_preferred_model: '非当前指定模型',
  capability_not_supported: '能力不匹配',
  quota_exhausted: '当前模型不可用',
}

const rejectedDetailLabels = {
  disabled: '请先在模型配置中心启用该模型，或选择其他可用模型。',
  model_disabled: '请先在模型配置中心启用该模型，或选择其他可用模型。',
  not_preferred_model: '当前请求已指定模型或策略默认模型，其他模型不会自动接管。',
  capability_not_supported: '该模型不支持当前图像生成场景或能力。',
  quota_exhausted: '该模型当前无法满足请求，可确认 fallback 模型后继续。',
}

const rejectedRescueLabels = {
  disabled: '前往模型配置中心启用模型。',
  model_disabled: '前往模型配置中心启用模型。',
  not_preferred_model: '清空手动模型或调整策略默认模型。',
  capability_not_supported: '选择支持当前场景的模型，或更新模型能力配置。',
  quota_exhausted: '使用可用的 fallback 模型重新预览。',
}

onMounted(() => {
  loadApprovedAssets()
  loadImageModels()
  loadStrategies()
})

function setMode(mode) {
  form.mode = mode
  error.value = ''
}

function createIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `image-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function assetUrl(asset) {
  return asset?.image_url || asset?.url || ''
}

function applyTaskResponse(response) {
  const data = response?.data?.data || response?.data || response || {}
  task.value = data.task || data || null
  assets.value = Array.isArray(data.assets) ? data.assets : []
}

function updateAsset(updated) {
  assets.value = assets.value.map(asset => (asset.id === updated.id ? { ...asset, ...updated } : asset))
}

function compactProviderOptions() {
  return Object.fromEntries(Object.entries(form.providerOptions)
    .filter(([, value]) => value !== '' && value !== null && value !== undefined))
}

function modeAcceptsSource(mode) {
  return ['image_to_image', 'image_to_image_set'].includes(mode)
}

function modeAcceptsReferences(mode) {
  return ['multi_reference_to_image', 'multi_reference_to_image_set'].includes(mode)
}

function schemaOptions(key, fallback) {
  const options = providerOptionSchema.value?.[key]?.options
  return Array.isArray(options) && options.length ? options : fallback
}

function buildModelParameterPayload() {
  const payload = {}
  if (form.modelId) payload.model_id = form.modelId
  if (form.size) payload.size = form.size
  if (form.output_format) payload.output_format = form.output_format
  if (form.response_format) payload.response_format = form.response_format
  if (form.watermark) payload.watermark = true
  const providerOptions = compactProviderOptions()
  if (Object.keys(providerOptions).length) {
    payload.provider_options = providerOptions
  }
  return payload
}

function addSourceAndReferences(payload) {
  if (modeAcceptsSource(form.mode) && form.sourceAssetId) {
    payload.source = { type: 'asset', asset_id: form.sourceAssetId, url: form.sourceUrl.trim() }
  } else if (modeAcceptsSource(form.mode) && form.sourceUrl.trim()) {
    payload.source = { url: form.sourceUrl.trim() }
  }
  if (modeAcceptsReferences(form.mode) && referenceImages.value.length) {
    payload.reference_images = referenceImages.value
  }
  return payload
}

function buildSelectionPreviewPayload() {
  const providerOptions = compactProviderOptions()
  if (form.watermark) {
    providerOptions.watermark = true
  }
  return addSourceAndReferences({
    mode: form.mode,
    prompt: form.prompt.trim(),
    destination_role: form.destination_role || selectedStrategy.value?.destination_role || '',
    strategy_id: selectedStrategy.value?.id || null,
    strategy_version: selectedStrategy.value?.version || null,
    model_id: form.modelId || null,
    count: Number(form.count) || 1,
    provider_options: providerOptions,
    size: form.size || null,
    output_format: form.output_format || null,
    response_format: form.response_format || null,
    watermark: Boolean(form.watermark),
  })
}

function buildAbPayload() {
  const payload = { ...buildSelectionPreviewPayload() }
  delete payload.strategy_id
  delete payload.strategy_version
  payload.strategy_ids = [...abSelectedStrategyIds.value]
  return payload
}

function buildPayload() {
  const hasConfirmedCurrentCost = Boolean(
    costConfirmed.value
      && selectionPreview.value?.selection_preview_id
      && selectionPreview.value?.request_hash
      && selectionPreview.value?.cost_estimate?.requires_confirmation,
  )
  const payload = addSourceAndReferences({
    mode: form.mode,
    prompt: form.prompt.trim(),
    count: Number(form.count) || 1,
    destination_role: form.destination_role,
    cost_confirmation: hasConfirmedCurrentCost,
    idempotency_key: createIdempotencyKey(),
    ...buildModelParameterPayload(),
  })
  if (selectedStrategy.value) {
    payload.strategy_id = selectedStrategy.value.id
    payload.strategy_version = selectedStrategy.value.version
  }
  if (selectionPreview.value?.selection_preview_id && selectionPreview.value?.request_hash) {
    payload.selection_preview_id = selectionPreview.value.selection_preview_id
    payload.selection_preview_request_hash = selectionPreview.value.request_hash
  }
  return payload
}

function resetSelectionPreview() {
  requiresFreshPreviewAfterHighCost.value = previewCostRequiresConfirmation.value || requiresFreshPreviewAfterHighCost.value
  selectionPreviewRequestToken.value += 1
  selectionPreview.value = null
  costConfirmed.value = false
  previewError.value = ''
  previewLoading.value = false
}

function clearAbWinnerRecommendation() {
  abRecommendationRequestToken.value += 1
  abWinnerRecommendation.value = null
  abRecommendationError.value = ''
  abRecommendationLoading.value = false
}

function resetAbPreview() {
  abRequestToken.value += 1
  abPreview.value = null
  abGroup.value = null
  clearAbWinnerRecommendation()
  abCostConfirmed.value = false
  abCreateIdempotencyKey.value = ''
  abCreateRequestHash.value = ''
  abError.value = ''
  abLoading.value = false
}

function abCreateKeyForPreview(requestHash) {
  if (!requestHash) return `ab-${createIdempotencyKey()}`
  if (!abCreateIdempotencyKey.value || abCreateRequestHash.value !== requestHash) {
    abCreateRequestHash.value = requestHash
    abCreateIdempotencyKey.value = `ab-${createIdempotencyKey()}`
  }
  return abCreateIdempotencyKey.value
}

function errorDetail(e) {
  return e?.response?.data?.detail || e?.response?.data?.message || e?.message || '操作失败，请稍后重试'
}

function errorText(value) {
  if (typeof value === 'string') return value
  if (!value) return '操作失败，请稍后重试'
  if (typeof value === 'object') {
    return value.user_message || value.message || value.detail || JSON.stringify(value)
  }
  return String(value)
}

function normalizeError(e) {
  return errorText(errorDetail(e))
}

function affectedTaskIdFromError(e) {
  const detail = errorDetail(e)
  if (!detail || typeof detail !== 'object' || !Array.isArray(detail.affected_ids)) return ''
  return detail.affected_ids[0] || ''
}

async function loadAffectedTaskFromError(e) {
  const affectedTaskId = affectedTaskIdFromError(e)
  if (!affectedTaskId) return false
  const response = await getImageTask(affectedTaskId)
  applyTaskResponse(response)
  return true
}

async function loadApprovedAssets() {
  try {
    const response = await listImageAssets({ status: 'approved', page_size: 30 })
    const data = response?.data?.data || response?.data || response || {}
    approvedAssets.value = Array.isArray(data.assets) ? data.assets : []
  } catch (e) {
    error.value = normalizeError(e)
  }
}

async function loadImageModels() {
  try {
    const response = await listModels({ model_type: 'image', enabled: true })
    const data = response?.data?.data || response?.data || response || {}
    imageModels.value = Array.isArray(data.models) ? data.models : []
    pruneProviderOptions()
  } catch (e) {
    error.value = normalizeError(e)
  }
}

async function loadStrategies() {
  try {
    const response = await listImageProductionStrategies({ status: 'active' })
    const data = response?.data?.data || response?.data || response || {}
    strategies.value = Array.isArray(data.strategies) ? data.strategies : []
  } catch (e) {
    error.value = normalizeError(e)
  }
}

function pruneProviderOptions() {
  const allowed = new Set(providerOptionFields.value.map(field => field.key))
  for (const key of Object.keys(form.providerOptions)) {
    if (!allowed.has(key)) delete form.providerOptions[key]
  }
}

function providerOptionLabel(key) {
  const labels = {
    sequential_image_generation: '连续组图',
    max_images: '最大图片数',
    stream: '流式输出',
    optimize_prompt_mode: '提示词优化',
    web_search: '联网增强',
  }
  return labels[key] || key
}

function rejectedReasonLabel(reason) {
  return rejectedReasonLabels[reason] || '未通过当前选择条件'
}

function rejectedDetailLabel(candidate) {
  return rejectedDetailLabels[candidate?.reason] || '该候选模型暂不适用于当前请求。'
}

function rejectedRescueLabel(candidate) {
  return rejectedRescueLabels[candidate?.reason] || '请调整模型、策略或 fallback 配置后重新预览。'
}

function fallbackCandidateLabel(candidate) {
  if (candidate?.confirmation_required || candidate?.risk_labels?.includes('requires_manual_confirmation')) {
    return '可作为 fallback 使用，创建前需要人工确认。'
  }
  return '可作为 fallback 使用。'
}

function timelineStatusLabel(status) {
  return timelineStatusLabels[status] || '未知'
}

function taskStatusLabel(status) {
  if (!status) return '尚未提交'
  return taskStatusLabels[status] || '未知'
}

function timelineStepLabel(step) {
  return timelineStepLabels[step?.key] || step?.label || step?.key || ''
}

function taskRescueActionLabel(action) {
  if (action?.type === 'retry_with_fallback_model') return '使用 fallback 模型重试'
  return '执行修复动作'
}

function isCurrentTimelineStep(step) {
  const current = taskTimeline.value.find(item => ['queued', 'running', 'blocked', 'failed'].includes(item.status))
  return current === step
}

function timelineStatusClass(status) {
  if (status === 'completed') return 'text-emerald-300'
  if (status === 'failed' || status === 'blocked') return 'text-rose-300'
  if (status === 'queued' || status === 'running') return 'text-sky-300'
  return 'text-slate-400'
}

function timelineDotClass(status) {
  if (status === 'completed') return 'bg-emerald-400'
  if (status === 'failed' || status === 'blocked') return 'bg-rose-400'
  if (status === 'queued' || status === 'running') return 'bg-sky-400'
  return 'bg-slate-600'
}

async function uploadSource(event) {
  const file = event.target.files?.[0]
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    const formData = new FormData()
    formData.append('file', file)
    const response = await uploadImageSource(formData)
    const data = response?.data?.data || response?.data || response || {}
    form.sourceUrl = data.url || ''
    form.sourceAssetId = ''
    resetSelectionPreview()
  } catch (e) {
    error.value = normalizeError(e)
  } finally {
    uploading.value = false
  }
}

function useApprovedAsset(asset) {
  form.sourceUrl = assetUrl(asset)
  form.sourceAssetId = asset.id || ''
  resetSelectionPreview()
}

function isReferenceAssetSelected(asset) {
  return form.referenceAssetIds.includes(asset.id)
}

function toggleReferenceAsset(asset) {
  if (!asset?.id) return
  if (isReferenceAssetSelected(asset)) {
    form.referenceAssetIds = form.referenceAssetIds.filter(id => id !== asset.id)
    resetSelectionPreview()
    return
  }
  form.referenceAssetIds = [...form.referenceAssetIds, asset.id]
  resetSelectionPreview()
}

async function previewAbComparison() {
  if (!abHasValidStrategyCount.value || abLoading.value) return
  const requestToken = abRequestToken.value + 1
  abRequestToken.value = requestToken
  abLoading.value = true
  abError.value = ''
  try {
    const response = await previewImageAbTest(buildAbPayload())
    if (requestToken !== abRequestToken.value) return
    const data = response?.data?.data || response?.data || response || {}
    if (abCreateRequestHash.value !== data.request_hash) {
      abCreateIdempotencyKey.value = ''
      abCreateRequestHash.value = ''
    }
    abPreview.value = data
    abGroup.value = null
    clearAbWinnerRecommendation()
    abCostConfirmed.value = false
  } catch (e) {
    if (requestToken !== abRequestToken.value) return
    abError.value = normalizeError(e)
  } finally {
    if (requestToken === abRequestToken.value) {
      abLoading.value = false
    }
  }
}

async function createAbComparison() {
  if (abCreateDisabled.value) return
  abLoading.value = true
  abError.value = ''
  clearAbWinnerRecommendation()
  try {
    const response = await createImageAbTest({
      ...buildAbPayload(),
      preview_request_hash: abPreview.value.request_hash,
      cost_confirmation: abCostConfirmed.value,
      idempotency_key: abCreateKeyForPreview(abPreview.value.request_hash),
    })
    const data = response?.data?.data || response?.data || response || {}
    abGroup.value = data.ab_group || data
  } catch (e) {
    abError.value = normalizeError(e)
  } finally {
    abLoading.value = false
  }
}

async function refreshAbComparison() {
  if (!abGroup.value?.id || abLoading.value) return
  const groupId = abGroup.value.id
  const requestToken = abRequestToken.value + 1
  abRequestToken.value = requestToken
  abLoading.value = true
  abError.value = ''
  clearAbWinnerRecommendation()
  try {
    const response = await refreshImageAbTest(groupId)
    if (requestToken !== abRequestToken.value || abGroup.value?.id !== groupId) return
    const data = response?.data?.data || response?.data || response || {}
    abGroup.value = data.ab_group || data
  } catch (e) {
    if (requestToken !== abRequestToken.value || abGroup.value?.id !== groupId) return
    abError.value = normalizeError(e)
  } finally {
    if (requestToken === abRequestToken.value && abGroup.value?.id === groupId) {
      abLoading.value = false
    }
  }
}

async function loadAbWinnerRecommendation() {
  if (!abGroup.value?.id || abRecommendationLoading.value) return
  const groupId = abGroup.value.id
  const requestToken = abRecommendationRequestToken.value + 1
  abRecommendationRequestToken.value = requestToken
  abRecommendationLoading.value = true
  abRecommendationError.value = ''
  try {
    const response = await getImageAbWinnerRecommendation(groupId)
    if (requestToken !== abRecommendationRequestToken.value || abGroup.value?.id !== groupId) return
    const data = response?.data?.data || response?.data || response || {}
    abWinnerRecommendation.value = data.recommendation || data.winner_recommendation || data
  } catch (e) {
    if (requestToken !== abRecommendationRequestToken.value || abGroup.value?.id !== groupId) return
    abWinnerRecommendation.value = null
    abRecommendationError.value = normalizeError(e)
  } finally {
    if (requestToken === abRecommendationRequestToken.value) {
      abRecommendationLoading.value = false
    }
  }
}

async function chooseAbWinner(attemptId) {
  const attempt = (abGroup.value?.attempts || []).find(item => item.id === attemptId)
  if (!abGroup.value?.id || !attemptId || abOutcomeDisabled.value || !attempt?.approved_asset_ready) return
  abLoading.value = true
  abError.value = ''
  try {
    const response = await chooseImageAbWinner(abGroup.value.id, attemptId, { reason: 'manual_selection' })
    const data = response?.data?.data || response?.data || response || {}
    abGroup.value = data.ab_group || data
  } catch (e) {
    abError.value = normalizeError(e)
  } finally {
    abLoading.value = false
  }
}

async function chooseAbNoWinner() {
  if (!abGroup.value?.id || abOutcomeDisabled.value) return
  abLoading.value = true
  abError.value = ''
  try {
    const response = await chooseImageAbNoWinner(abGroup.value.id, { reason: 'manual_no_winner' })
    const data = response?.data?.data || response?.data || response || {}
    abGroup.value = data.ab_group || data
  } catch (e) {
    abError.value = normalizeError(e)
  } finally {
    abLoading.value = false
  }
}

async function runSelectionPreview() {
  const payload = buildSelectionPreviewPayload()
  const requestToken = selectionPreviewRequestToken.value + 1
  selectionPreviewRequestToken.value = requestToken
  previewLoading.value = true
  previewError.value = ''
  try {
    const response = await previewImageSelection(payload)
    if (requestToken !== selectionPreviewRequestToken.value) return
    const data = response?.data?.data || response?.data || response || {}
    selectionPreview.value = data
    costConfirmed.value = false
    requiresFreshPreviewAfterHighCost.value = false
  } catch (e) {
    if (requestToken !== selectionPreviewRequestToken.value) return
    previewError.value = normalizeError(e)
  } finally {
    if (requestToken === selectionPreviewRequestToken.value) {
      previewLoading.value = false
    }
  }
}

async function handleRescueAction(action) {
  if (action?.type !== 'confirm_fallback_model' || !action.model_id) return
  form.modelId = action.model_id
  await nextTick()
  await runSelectionPreview()
}

async function handleTaskRescueAction(action) {
  if (action?.type !== 'retry_with_fallback_model' || !action.model_id) return
  form.modelId = action.model_id
  resetSelectionPreview()
  await nextTick()
  await runSelectionPreview()
}

async function submit() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    const response = await createImageTask(buildPayload())
    applyTaskResponse(response)
  } catch (e) {
    error.value = normalizeError(e)
    try {
      await loadAffectedTaskFromError(e)
    } catch {
      // Keep the original create error visible when the failed task cannot be fetched.
    }
  } finally {
    submitting.value = false
  }
}

async function refreshTask() {
  if (!task.value?.id || syncing.value) return
  syncing.value = true
  error.value = ''
  try {
    const response = await getImageTask(task.value.id)
    applyTaskResponse(response)
  } catch (e) {
    error.value = normalizeError(e)
  } finally {
    syncing.value = false
  }
}

async function syncTask() {
  if (!task.value?.id || syncing.value) return
  syncing.value = true
  error.value = ''
  try {
    const response = await syncImageTask(task.value.id)
    applyTaskResponse(response)
  } catch (e) {
    error.value = normalizeError(e)
  } finally {
    syncing.value = false
  }
}

async function dispatchQueuedTask() {
  if (!task.value?.id || syncing.value) return
  syncing.value = true
  error.value = ''
  try {
    const response = await dispatchQueuedImageTask(task.value.id)
    applyTaskResponse(response)
  } catch (e) {
    error.value = normalizeError(e)
  } finally {
    syncing.value = false
  }
}

function assetAllowed(asset, action) {
  return Array.isArray(asset?.allowed_actions) && asset.allowed_actions.includes(action)
}

function canPromoteAsset(asset) {
  const context = asset?.destination_context || {}
  return assetAllowed(asset, 'promote_to_video_asset')
    && Boolean(context.video_run_id || context.run_id)
    && Boolean(context.frame_id)
}

function assetReviewGateLabel(gate) {
  if (gate?.status === 'approved') return '已通过'
  if (gate?.status === 'manual_review_pending') return '待人工审查'
  if (gate?.status === 'ai_review_pending') return '待 AI 审查'
  if (gate?.status === 'blocked') return '已阻塞'
  if (gate?.status === 'rejected') return '已驳回'
  return '未开始'
}

async function reviewAsset(asset, action) {
  if (!asset.id) return
  error.value = ''
  try {
    const response = await reviewImageAsset(asset.id, { action, asset_version: asset.version })
    const data = response?.data?.data || response?.data || response || {}
    if (data.asset) updateAsset(data.asset)
    if (action === 'approve') loadApprovedAssets()
  } catch (e) {
    error.value = normalizeError(e)
  }
}

async function promoteAsset(asset) {
  if (!asset.id) return
  const context = asset.destination_context || {}
  const runId = context.video_run_id || context.run_id
  const frameId = context.frame_id
  if (!runId || !frameId) {
    error.value = '该图像缺少视频生产目标，不能直接推广到视频。'
    return
  }
  error.value = ''
  try {
    const payload = {
      run_id: runId,
      frame_id: frameId,
      asset_version: asset.version,
    }
    const episodeId = context.episode_id || asset.episode_id || task.value?.episode_id
    if (episodeId) payload.episode_id = episodeId
    await promoteImageAssetToVideo(asset.id, payload)
    updateAsset({ ...asset, downstream_promoted: true })
  } catch (e) {
    error.value = normalizeError(e)
  }
}

async function createTaskFromAsset(asset, action) {
  if (!asset.id) return
  error.value = ''
  try {
    const response = await editImageAsset(asset.id, {
      mode: 'image_to_image',
      action,
      asset_version: asset.version,
      prompt: form.prompt.trim() || asset.prompt || '基于当前资产继续编辑',
      count: 1,
      destination_role: form.destination_role,
      reference_images: referenceImages.value,
      cost_confirmation: false,
      idempotency_key: createIdempotencyKey(),
      ...buildModelParameterPayload(),
    })
    applyTaskResponse(response)
  } catch (e) {
    error.value = normalizeError(e)
  }
}

async function editAgain(asset) {
  if (!assetAllowed(asset, 'repaint')) return
  await createTaskFromAsset(asset, 'repaint')
}

async function copyAsNewTask(asset) {
  if (!assetAllowed(asset, 'copy_as_new_task')) return
  await createTaskFromAsset(asset, 'copy_as_new_task')
}

watch(
  () => [
    form.mode,
    form.prompt,
    form.destination_role,
    form.count,
    form.sourceUrl,
    form.sourceAssetId,
    form.referenceUrls,
    form.referenceAssetIds.join(','),
    form.modelId,
    form.size,
    form.output_format,
    form.response_format,
    form.watermark,
    selectedStrategyId.value,
    JSON.stringify(compactProviderOptions()),
  ],
  () => {
    resetSelectionPreview()
    resetAbPreview()
  },
)

watch(
  () => abSelectedStrategyIds.value.join(','),
  resetAbPreview,
)
</script>
