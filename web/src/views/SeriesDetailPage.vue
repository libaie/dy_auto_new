<template>
  <div class="p-6">
    <button @click="$router.push('/series')" class="text-sky-400 hover:text-sky-300 mb-4 transition cursor-pointer">&larr; 返回系列列表</button>
    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <template v-else-if="series">
      <div class="flex justify-between items-start mb-6">
        <div>
          <h1 class="text-2xl font-bold text-slate-100">{{ series.title }}</h1>
          <p class="text-slate-400 mt-1">{{ series.logline }}</p>
          <div class="flex gap-3 mt-2 text-sm text-slate-500">
            <span>{{ series.total_episodes }} 集</span><span>{{ series.genre }}</span>
            <span>{{ series.mode === 'fully_automatic' ? '全自动' : '逐步确认' }}</span>
            <span :class="styleLock?.locked ? 'text-emerald-400' : 'text-amber-400'">
              {{ styleLock?.locked ? `风格已锁定 v${styleLock.version || 1}` : '风格未锁定' }}
            </span>
          </div>
        </div>
        <div class="flex gap-2">
          <button data-test="edit-series" @click="beginEditSeries"
                  class="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            编辑系列
          </button>
          <button data-test="lock-style" @click="lockStyle" :disabled="styleLockInProgress"
                  class="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            {{ styleLockInProgress ? '锁定中...' : (styleLock?.locked ? '重新锁定风格' : '锁定风格') }}
          </button>
          <button data-test="generate-story-plan" @click="generateStoryPlan" :disabled="storyPlanButtonDisabled"
                  class="bg-fuchsia-600 hover:bg-fuchsia-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            {{ storyPlanButtonText }}
          </button>
          <button @click="$router.push(`/series/${series.id}/agency-console`)"
                  class="bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            专家团队控制台
          </button>
          <button @click="$router.push(`/series/${series.id}/ai-text-artifacts`)"
                  class="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            AI 文本追溯台
          </button>
          <button v-if="!series.character_count && !series.scene_count && series.logline" @click="autoGenerate"
                  :disabled="autoGenerating" class="bg-purple-500 hover:bg-purple-400 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer"
                  title="根据故事概要，AI 自动生成角色和场景">
            {{ autoGenerating ? 'AI 生成中...' : 'AI 一键生成角色&场景' }}
          </button>
          <button data-test="start-pipeline" @click="startPipelineRun" :disabled="pipelineStartDisabled"
                  class="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            {{ pipelineButtonText }}
          </button>
          <button @click="deleteDialogOpen = true"
                  class="border border-red-500/40 bg-red-500/10 hover:bg-red-500/20 text-red-300 px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            安全归档
          </button>
        </div>
      </div>

      <div v-if="editingSeries" class="mb-6 rounded-xl border border-slate-700 bg-slate-950/50 p-4">
        <div v-if="saveError" class="mb-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          {{ saveError }}
        </div>
        <div class="grid gap-3 md:grid-cols-2">
          <label class="block text-sm text-slate-300">
            <span class="mb-1 block">标题</span>
            <input data-test="series-title-input" v-model="seriesForm.title" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100 border border-slate-700" />
          </label>
          <label class="block text-sm text-slate-300">
            <span class="mb-1 block">类型</span>
            <input v-model="seriesForm.genre" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100 border border-slate-700" />
          </label>
          <label class="block text-sm text-slate-300">
            <span class="mb-1 block">目标时长</span>
            <input v-model.number="seriesForm.target_duration" type="number" min="1" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100 border border-slate-700" />
          </label>
          <label class="block text-sm text-slate-300">
            <span class="mb-1 block">制作模式</span>
            <select v-model="seriesForm.mode" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100 border border-slate-700">
              <option value="fully_automatic">全自动</option>
              <option value="step_by_step">逐步确认</option>
            </select>
          </label>
        </div>
        <label class="mt-3 block text-sm text-slate-300">
          <span class="mb-1 block">故事梗概</span>
          <textarea v-model="seriesForm.logline" rows="3" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100 border border-slate-700" />
        </label>
        <label class="mt-3 flex items-center gap-2 text-sm text-slate-300">
          <input v-model="seriesForm.pilot_first" type="checkbox" class="rounded border-slate-600 bg-slate-900" />
          <span>先制作试播集</span>
        </label>
        <div class="mt-4 flex justify-end gap-2">
          <button @click="editingSeries = false" class="rounded border border-slate-700 px-4 py-2 text-sm text-slate-300">取消</button>
          <button data-test="save-series" @click="saveSeries" :disabled="savingSeries"
                  class="rounded bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-50">
            {{ savingSeries ? '保存中...' : '保存系列' }}
          </button>
        </div>
      </div>

      <div v-if="deleteResult" class="mb-6 rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">
        {{ deleteResult }}
      </div>

      <div v-if="styleLock" class="rounded-xl border border-gray-700/50 px-4 py-3 mb-6 text-sm text-slate-400" style="background: rgba(15, 23, 42, 0.5);">
        <div class="flex flex-wrap gap-4">
          <span>角色参考图 {{ styleLock.reference_status?.characters?.ready || 0 }}/{{ styleLock.reference_status?.characters?.total || 0 }}</span>
          <span>场景参考图 {{ styleLock.reference_status?.scenes?.ready || 0 }}/{{ styleLock.reference_status?.scenes?.total || 0 }}</span>
          <span v-if="styleLock.missing_assets?.length" class="text-amber-300">待补资产 {{ styleLock.missing_assets.length }}</span>
          <span v-if="styleLock.agency_team_status?.enabled" class="text-cyan-300">
            专家团队 {{ styleLock.agency_team_status.core_role_count || 0 }} 核心 / {{ styleLock.agency_team_status.support_role_count || 0 }} 支援
          </span>
        </div>
      </div>

      <div v-if="storyPlanError || storyPlanResult || storyPlanEpisodeCount || storyPlanSeriesArtifact" data-test="story-plan-status" class="rounded-xl border border-gray-700/50 px-4 py-3 mb-6 text-sm text-slate-400" style="background: rgba(15, 23, 42, 0.5);">
        <div class="flex flex-wrap gap-4">
          <span>故事规划 {{ storyPlanEpisodeCount }}/{{ targetEpisodeCount }} 集</span>
          <span v-if="storyPlanSeriesArtifact" :class="storyPlanSourceClass">{{ storyPlanSourceText }}</span>
          <span v-if="storyPlanError" class="text-red-300">{{ storyPlanError }}</span>
        </div>
      </div>

      <div class="grid gap-4 lg:grid-cols-2 mb-6">
        <section class="rounded-xl border border-slate-700 bg-slate-950/50 p-4">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-lg font-semibold text-slate-100">关联角色</h2>
            <span class="text-xs text-slate-500">{{ (series.characters || []).length }} 个</span>
          </div>
          <div v-if="unlinkErrors.character" class="mb-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            {{ unlinkErrors.character }}
          </div>
          <div v-if="!(series.characters || []).length" class="text-sm text-slate-500">尚未关联角色</div>
          <div v-for="character in series.characters || []" :key="character.id" class="mb-2 flex items-center justify-between gap-3 rounded bg-slate-900/60 p-3">
            <div class="flex min-w-0 items-center gap-3">
              <div v-if="linkedCharacterReferences(character).length" class="flex max-w-[13rem] shrink-0 flex-wrap gap-1.5">
                <a
                  v-for="slot in linkedCharacterReferences(character)"
                  :key="slot.key"
                  :href="slot.src"
                  target="_blank"
                  rel="noreferrer"
                  class="relative block h-12 w-12 overflow-hidden rounded border border-slate-700"
                >
                  <img
                    :data-test="`linked-character-reference-${character.id}-${slot.key}`"
                    :src="slot.src"
                    :alt="`${character.name} ${slot.label}参考图`"
                    class="h-full w-full object-cover"
                  >
                  <span class="absolute inset-x-0 bottom-0 truncate bg-slate-950/80 px-1 py-0.5 text-center text-[10px] text-slate-100">{{ slot.label }}</span>
                </a>
              </div>
              <div v-else class="flex h-12 w-12 shrink-0 items-center justify-center rounded border border-slate-700 text-xs text-slate-500">
                {{ hasRawReference(character, CHARACTER_REFERENCE_SLOT_DEFS) ? '链接无效' : '待生成' }}
              </div>
              <div class="min-w-0">
                <div class="truncate text-sm text-slate-100">{{ character.name }}</div>
                <div class="text-xs text-slate-500">{{ character.role_type }}</div>
                <div v-if="linkedCharacterReferences(character).length" class="text-xs text-cyan-300">
                  参考图 {{ linkedCharacterReferences(character).length }}/{{ CHARACTER_REFERENCE_SLOT_DEFS.length }}
                </div>
                <span v-else-if="hasRawReference(character, CHARACTER_REFERENCE_SLOT_DEFS)" class="text-xs text-red-300">链接无效</span>
              </div>
            </div>
            <button :data-test="`unlink-character-${character.id}`" class="shrink-0 rounded border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800" @click="removeCharacter(character.id)">
              取消关联
            </button>
          </div>
        </section>

        <section class="rounded-xl border border-slate-700 bg-slate-950/50 p-4">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-lg font-semibold text-slate-100">关联场景</h2>
            <span class="text-xs text-slate-500">{{ (series.scenes || []).length }} 个</span>
          </div>
          <div v-if="unlinkErrors.scene" class="mb-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            {{ unlinkErrors.scene }}
          </div>
          <div v-if="!(series.scenes || []).length" class="text-sm text-slate-500">尚未关联场景</div>
          <div v-for="scene in series.scenes || []" :key="scene.id" class="mb-2 flex items-center justify-between gap-3 rounded bg-slate-900/60 p-3">
            <div class="flex min-w-0 items-center gap-3">
              <div v-if="linkedSceneReferences(scene).length" class="flex max-w-[10rem] shrink-0 flex-wrap gap-1.5">
                <a
                  v-for="slot in linkedSceneReferences(scene)"
                  :key="slot.key"
                  :href="slot.src"
                  target="_blank"
                  rel="noreferrer"
                  class="relative block h-12 w-12 overflow-hidden rounded border border-slate-700"
                >
                  <img
                    :data-test="`linked-scene-reference-${scene.id}-${slot.key}`"
                    :src="slot.src"
                    :alt="`${scene.name} ${slot.label}参考图`"
                    class="h-full w-full object-cover"
                  >
                  <span class="absolute inset-x-0 bottom-0 truncate bg-slate-950/80 px-1 py-0.5 text-center text-[10px] text-slate-100">{{ slot.label }}</span>
                </a>
              </div>
              <div v-else class="flex h-12 w-12 shrink-0 items-center justify-center rounded border border-slate-700 text-xs text-slate-500">
                {{ hasRawReference(scene, SCENE_REFERENCE_SLOT_DEFS) ? '链接无效' : '待生成' }}
              </div>
              <div class="min-w-0">
                <div class="truncate text-sm text-slate-100">{{ scene.name }}</div>
                <div class="text-xs text-slate-500">{{ scene.scene_type }}</div>
                <div v-if="linkedSceneReferences(scene).length" class="text-xs text-cyan-300">
                  参考图 {{ linkedSceneReferences(scene).length }}/{{ SCENE_REFERENCE_SLOT_DEFS.length }}
                </div>
                <span v-else-if="hasRawReference(scene, SCENE_REFERENCE_SLOT_DEFS)" class="text-xs text-red-300">链接无效</span>
              </div>
            </div>
            <button :data-test="`unlink-scene-${scene.id}`" class="shrink-0 rounded border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800" @click="removeScene(scene.id)">
              取消关联
            </button>
          </div>
        </section>
      </div>

      <div class="rounded-xl border border-gray-700/50 overflow-hidden" style="background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(12px);">
        <div class="px-5 py-3 border-b border-gray-700/50 font-medium text-slate-200">剧集列表</div>
        <div v-if="aiTextArtifactsError" class="border-b border-red-500/30 bg-red-950/30 px-5 py-3 text-sm text-red-200">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <span>AI 文本加载失败：{{ aiTextArtifactsError }}</span>
            <button data-test="retry-ai-text-artifacts" type="button" class="rounded border border-red-400/40 px-3 py-1.5 text-xs text-red-100 hover:bg-red-900/50" @click="refreshEpisodeTextArtifacts">
              重试
            </button>
          </div>
        </div>
        <div class="divide-y divide-gray-700/30 max-h-[600px] overflow-y-auto">
          <div v-for="ep in episodes" :key="ep.id" class="hover:bg-gray-800/40 transition">
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-slate-500 w-12 text-sm">E{{ String(ep.episode_number).padStart(2, '0') }}</span>
              <span class="min-w-0 flex-1 text-sm text-slate-200">{{ ep.title || '未命名' }}</span>
              <span class="hidden text-xs text-slate-500 sm:inline">{{ hasEpisodeScript(ep) ? '剧本已生成' : '剧本待生成' }}</span>
              <span class="hidden text-xs text-slate-500 sm:inline">{{ storyboardFrameCount(ep) ? `分镜 ${storyboardFrameCount(ep)} 镜头` : '分镜待生成' }}</span>
              <span class="text-xs text-slate-500 w-16 text-right">{{ ep.duration_seconds ? ep.duration_seconds + 's' : '-' }}</span>
              <span :class="epStatusClass(ep.status)" class="px-2 py-1 rounded text-xs">{{ ep.status }}</span>
              <button
                :data-test="`episode-text-toggle-${ep.id}`"
                type="button"
                class="shrink-0 rounded border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800"
                @click="toggleEpisodeText(ep.id)"
              >
                {{ expandedEpisodeId === ep.id ? '收起文本' : '查看文本' }}
              </button>
            </div>
            <div v-if="expandedEpisodeId === ep.id" class="border-t border-slate-800/70 bg-slate-950/50 px-5 py-4">
              <div v-if="episodeOutlineText(ep)" class="mb-4 rounded border border-slate-800 bg-slate-950/70 p-3">
                <div class="mb-2 text-xs font-medium text-cyan-300">剧集大纲</div>
                <pre class="max-h-44 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-300">{{ episodeOutlineText(ep) }}</pre>
              </div>
              <div class="mb-4 grid gap-3 md:grid-cols-2">
                <section class="rounded border border-slate-800 bg-slate-950/70 p-3">
                  <h3 class="text-xs font-medium text-slate-200">本集角色</h3>
                  <div v-if="episodeAssetCharacters(ep).length" class="mt-2 flex flex-wrap gap-2">
                    <span
                      v-for="character in episodeAssetCharacters(ep)"
                      :key="character.id"
                      class="rounded bg-slate-800 px-2 py-1 text-xs text-slate-200"
                    >
                      {{ character.name || character.id }}
                      <span v-if="character.source === 'generated'" class="ml-1 text-emerald-300">新增</span>
                    </span>
                  </div>
                  <p v-else class="mt-2 text-xs text-amber-300">缺少本集角色</p>
                </section>
                <section class="rounded border border-slate-800 bg-slate-950/70 p-3">
                  <h3 class="text-xs font-medium text-slate-200">本集场景</h3>
                  <div v-if="episodeAssetScenes(ep).length" class="mt-2 flex flex-wrap gap-2">
                    <span
                      v-for="scene in episodeAssetScenes(ep)"
                      :key="scene.id"
                      class="rounded bg-slate-800 px-2 py-1 text-xs text-slate-200"
                    >
                      {{ scene.name || scene.id }}
                      <span v-if="scene.source === 'generated'" class="ml-1 text-emerald-300">新增</span>
                    </span>
                  </div>
                  <p v-else class="mt-2 text-xs text-amber-300">缺少本集场景</p>
                </section>
              </div>
              <p v-if="episodeAssetMissing(ep)" class="mb-4 text-xs text-amber-300">缺少本集角色或场景</p>
              <div v-if="episodeGeneratedAssets(ep).length" class="mb-4 rounded border border-emerald-900/60 bg-emerald-950/20 p-3 text-xs text-emerald-100">
                <span class="font-medium">本集新增资产</span>
                <span class="ml-2">{{ episodeGeneratedAssets(ep).join('、') }}</span>
              </div>
              <div class="grid gap-4 lg:grid-cols-2">
                <section class="rounded border border-slate-800 bg-slate-950/70 p-3">
                  <div class="mb-2 flex items-center justify-between gap-3">
                    <h3 class="text-xs font-medium text-slate-200">剧本</h3>
                    <div class="flex items-center gap-2">
                      <button
                        v-if="!hasEpisodeScript(ep)"
                        :data-test="`generate-episode-script-${ep.id}`"
                        class="rounded border border-fuchsia-500/40 px-2 py-1 text-[11px] text-fuchsia-100 hover:bg-fuchsia-950/40 disabled:opacity-50"
                        :disabled="episodeScriptGenerating[ep.id]"
                        @click.stop="generateScriptForEpisode(ep)"
                      >{{ episodeScriptGenerating[ep.id] ? '生成中...' : '生成剧本/分镜' }}</button>
                      <span class="text-[11px] text-slate-500">{{ hasEpisodeScript(ep) ? '已生成' : '尚未生成' }}</span>
                    </div>
                  </div>
                  <p v-if="episodeScriptErrors[ep.id]" class="mb-2 text-xs text-rose-300">{{ episodeScriptErrors[ep.id] }}</p>
                  <pre class="max-h-72 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-300">{{ episodeScriptText(ep) || '剧本尚未生成' }}</pre>
                </section>
                <section class="rounded border border-slate-800 bg-slate-950/70 p-3">
                  <div class="mb-2 flex items-center justify-between gap-3">
                    <h3 class="text-xs font-medium text-slate-200">分镜剧本</h3>
                    <div class="flex items-center gap-2">
                      <button
                        v-if="storyboardFrameCount(ep)"
                        :data-test="`generate-missing-storyboard-images-${ep.id}`"
                        class="rounded border border-sky-500/40 px-2 py-1 text-[11px] text-sky-200 hover:bg-sky-950/40 disabled:opacity-50"
                        :disabled="storyboardImageBusy[ep.id] === 'batch'"
                        @click.stop="generateMissingFrameImages(ep)"
                      >{{ storyboardImageBusy[ep.id] === 'batch' ? '生成中...' : '生成缺失分镜图' }}</button>
                      <span class="text-[11px] text-slate-500">{{ storyboardFrameCount(ep) ? `${storyboardFrameCount(ep)} 镜头` : '尚未生成' }}</span>
                    </div>
                  </div>
                  <div v-if="storyboardFrames(ep).length" class="space-y-3">
                    <article v-for="(frame, index) in storyboardFrames(ep)" :key="frame.frame_id || frame.shot_id || index" class="rounded border border-slate-800/80 bg-slate-900/40 p-3">
                      <div class="mb-2 flex items-center justify-between gap-3 text-xs">
                        <span class="font-medium text-slate-200">镜头 {{ index + 1 }}</span>
                        <span class="text-slate-500">{{ frame.time_range || `${frame.duration || frame.duration_seconds || '-'}s` }}</span>
                      </div>
                      <p v-if="frame.narration || frame.dialogue || frame.voiceover" class="whitespace-pre-wrap text-xs leading-5 text-slate-300">{{ frame.narration || frame.dialogue || frame.voiceover }}</p>
                      <p v-if="frame.image_prompt" class="mt-2 whitespace-pre-wrap text-xs leading-5 text-sky-200">{{ frame.image_prompt }}</p>
                      <p v-if="frame.video_prompt || frame.action" class="mt-2 whitespace-pre-wrap text-xs leading-5 text-emerald-200">{{ frame.video_prompt || frame.action }}</p>
                      <div class="mt-3 border-t border-slate-800 pt-3">
                        <div class="flex items-center justify-between gap-3 text-xs">
                          <span class="font-medium text-slate-200">分镜图</span>
                          <span :class="storyboardImageStatusClass(storyboardImageForFrame(ep, frame, index)?.status)">
                            {{ storyboardImageStatusLabel(storyboardImageForFrame(ep, frame, index)?.status) }}
                          </span>
                        </div>
                        <div v-if="storyboardImageUrl(ep, frame, index)" class="mt-2 flex items-center gap-3">
                          <img
                            class="h-20 w-32 rounded border border-slate-800 object-cover"
                            :src="storyboardImageUrl(ep, frame, index)"
                            :alt="`分镜图 ${frame.time_range || `镜头 ${index + 1}`}`"
                          >
                          <span class="text-[11px] text-slate-500">{{ storyboardImageForFrame(ep, frame, index)?.asset?.id || '已生成' }}</span>
                        </div>
                        <p v-else class="mt-2 text-[11px] text-slate-500">分镜图未生成</p>
                        <button
                          class="mt-2 rounded border border-slate-700 px-2 py-1 text-[11px] text-slate-200 hover:bg-slate-800 disabled:opacity-50"
                          :data-test="`generate-storyboard-image-${ep.id}-${storyboardFrameIdentity(frame, index)}`"
                          :disabled="storyboardImageBusy[`${ep.id}:${storyboardFrameIdentity(frame, index)}`] === 'single'"
                          @click.stop="generateFrameImage(ep, frame, index)"
                        >{{ storyboardImageBusy[`${ep.id}:${storyboardFrameIdentity(frame, index)}`] === 'single' ? '生成中...' : '生成分镜图' }}</button>
                      </div>
                    </article>
                  </div>
                  <p v-if="storyboardImageErrors[ep.id]" class="mt-2 text-xs text-rose-300">{{ storyboardImageErrors[ep.id] }}</p>
                  <pre v-if="!storyboardFrames(ep).length" class="max-h-72 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-300">{{ episodeStoryboardText(ep) || '分镜剧本尚未生成' }}</pre>
                </section>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="runs.length" class="mt-8">
        <h2 class="text-lg font-semibold text-slate-100 mb-3">流水线运行历史</h2>
        <div class="space-y-2">
          <div v-for="r in runs" :key="r.id" @click="$router.push(`/pipeline/${r.id}`)"
               class="rounded-lg border border-gray-700/50 px-4 py-3 flex items-center gap-4 hover:shadow-lg hover:shadow-sky-900/10 transition cursor-pointer"
               style="background: rgba(15, 23, 42, 0.5);">
            <span class="text-xs text-slate-500 font-mono">{{ r.id.slice(0, 8) }}</span>
            <span :class="runStatusClass(r.status)" class="px-2 py-1 rounded text-xs">{{ r.status }}</span>
            <span class="text-xs text-slate-500">Layer {{ r.current_layer }}/6</span>
            <span class="text-xs text-slate-500 ml-auto">{{ r.created_at?.slice(0, 19) }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- AI 自动生成进度对话框 -->
    <div v-if="autoGenerating || autoGenResult" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="autoGenResult = null; load()">
      <div class="rounded-xl p-6 w-full max-w-lg shadow-2xl border border-gray-700/50 max-h-[85vh] overflow-y-auto" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">AI 自动生成</h2>
        <template v-if="autoGenerating">
          <div class="text-center py-8">
            <div class="animate-spin w-8 h-8 border-2 border-purple-400 border-t-transparent rounded-full mx-auto mb-3"></div>
            <p class="text-sm text-slate-400">{{ autoGenStep }}</p>
          </div>
        </template>
        <template v-else-if="autoGenResult">
          <p class="text-xs text-slate-500 mb-4">AI 已根据故事概要生成以下资产：</p>
          <div v-if="autoGenResult.characters?.length" class="mb-4">
            <h3 class="text-sm font-medium text-slate-200 mb-2">角色 ({{ autoGenResult.characters.length }})</h3>
            <div class="space-y-1">
              <div v-for="(c, i) in autoGenResult.characters" :key="'c'+i" class="text-xs text-slate-400 flex gap-2">
                <span class="text-slate-100">{{ c.name }}</span>
                <span class="text-slate-500">· {{ c.role_type }} · {{ c.gender === 'male' ? '男' : '女' }}</span>
              </div>
            </div>
          </div>
          <div v-if="autoGenResult.scenes?.length" class="mb-4">
            <h3 class="text-sm font-medium text-slate-200 mb-2">场景 ({{ autoGenResult.scenes.length }})</h3>
            <div class="space-y-1">
              <div v-for="(sc, i) in autoGenResult.scenes" :key="'s'+i" class="text-xs text-slate-400 flex gap-2">
                <span class="text-slate-100">{{ sc.name }}</span>
                <span class="text-slate-500">· {{ sc.scene_type }} · {{ sc.lighting }}</span>
              </div>
            </div>
          </div>
          <div class="flex justify-end mt-4">
            <button @click="autoGenResult = null; load()" class="px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition cursor-pointer text-sm">完成</button>
          </div>
        </template>
      </div>
    </div>

    <DangerConfirmDialog
      :open="deleteDialogOpen"
      title="确认安全归档"
      message="系统会根据后端判断执行归档或删除，并保留已有生产记录。"
      :impact="deleteError || '不会从前端直接清理生产素材。'"
      :confirm-text="deletingSeries ? '处理中...' : '确认执行'"
      @cancel="deleteDialogOpen = false"
      @confirm="removeSeries"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSeries, ensureSeriesEpisodes, generateSeriesStoryPlan, generateEpisodeScript, autoGenerateAssets, getStyleLock, lockSeriesStyle, updateSeries, deleteSeries, unlinkCharacter, unlinkScene } from '../api/series.js'
import { listRuns } from '../api/pipeline.js'
import { startEpisodeProduction } from '../api/videoProduction.js'
import { listAITextArtifacts } from '../api/aiTextArtifacts.js'
import { createMissingStoryboardImageTasks, createStoryboardFrameImageTask, getStoryboardImageState } from '../api/storyboardImages.js'
import DangerConfirmDialog from '../components/assets/DangerConfirmDialog.vue'
const route = useRoute(); const router = useRouter(); const series = ref(null); const episodes = ref([]); const runs = ref([]); const styleLock = ref(null); const loading = ref(true); const pipelineStarting = ref(false); const styleLocking = ref(false); const error = ref('')
const autoGenerating = ref(false); const autoGenStep = ref(''); const autoGenResult = ref(null)
const storyPlanning = ref(false); const storyPlanError = ref(''); const storyPlanResult = ref(null)
const editingSeries = ref(false); const savingSeries = ref(false); const saveError = ref('')
const seriesForm = reactive({ title: '', logline: '', genre: '', target_duration: 60, mode: 'step_by_step', pilot_first: true })
const unlinkErrors = reactive({ character: '', scene: '' })
const deleteDialogOpen = ref(false); const deletingSeries = ref(false); const deleteError = ref(''); const deleteResult = ref('')
const styleLockPollTimer = ref(null)
const storyPlanPollTimer = ref(null)
const expandedEpisodeId = ref('')
const aiTextArtifacts = ref([])
const aiTextArtifactsError = ref('')
const storyboardImageState = ref({})
const storyboardImageBusy = reactive({})
const storyboardImageErrors = reactive({})
const episodeScriptGenerating = reactive({})
const episodeScriptErrors = reactive({})
const autostartRequested = ref(route.query?.autostart === 'production')
const autostartRunning = ref(false)
const MANAGED_IMAGE_PREFIXES = ['/static/', '/api/image-creation/pixelle-files/']
const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]', '::1'])
const CHARACTER_REFERENCE_SLOT_DEFS = [
  { key: 'avatar_front_url', label: '正面' },
  { key: 'avatar_side_url', label: '侧面' },
  { key: 'avatar_threequarter_url', label: '三分之四' },
  { key: 'avatar_fullbody_url', label: '全身' },
]
const SCENE_REFERENCE_SLOT_DEFS = [
  { key: 'reference_wideshot_url', label: '广角' },
  { key: 'reference_midshot_url', label: '中景' },
  { key: 'reference_aerial_url', label: '俯拍' },
]
const CHARACTER_REFERENCE_SLOT_KEYS = new Set(CHARACTER_REFERENCE_SLOT_DEFS.map((slot) => slot.key))
const SCENE_REFERENCE_SLOT_KEYS = new Set(SCENE_REFERENCE_SLOT_DEFS.map((slot) => slot.key))
const finishedEpisodeStatuses = new Set(['done', 'completed'])
const busyEpisodeStatuses = new Set(['rendering'])
const plannedVideoRunStatuses = new Set(['draft', 'storyboard_ready'])
const activeVideoRunStatuses = new Set([
  'draft',
  'storyboard_ready',
  'image_batch_running',
  'image_generation',
  'image_review_pending',
  'image_human_review_required',
  'image_approved',
  'video_batch_running',
  'video_generation',
  'video_review_pending',
  'video_human_review_required',
  'video_segments_approved',
  'composing',
  'composition',
])
function episodeHasActiveVideoRun(ep) {
  return Boolean(ep.active_video_run_id) || activeVideoRunStatuses.has(ep.video_run_status)
}
function episodeHasProducingVideoRun(ep) {
  return activeVideoRunStatuses.has(ep.video_run_status) && !plannedVideoRunStatuses.has(ep.video_run_status)
}
function episodeIsBusy(ep) {
  return busyEpisodeStatuses.has(ep.status) || episodeHasActiveVideoRun(ep)
}
function episodeVideoRunRoute(ep) {
  return ep?.video_run_route || (ep?.active_video_run_id ? `/video-production/${ep.active_video_run_id}` : '')
}
function episodeStoryboardImageParams(ep) {
  const params = { series_id: series.value.id }
  if (ep?.active_video_run_id) params.run_id = ep.active_video_run_id
  return params
}
const runnableEpisode = computed(() => episodes.value.find(ep => (
  !finishedEpisodeStatuses.has(ep.status) && !episodeIsBusy(ep)
)) || null)
const activeProductionEpisode = computed(() => episodes.value.find(ep => episodeHasActiveVideoRun(ep)) || null)
const activeProductionRoute = computed(() => episodeVideoRunRoute(activeProductionEpisode.value))
const canContinueActiveProduction = computed(() => !runnableEpisode.value && Boolean(activeProductionRoute.value))
const hasBusyEpisode = computed(() => episodes.value.some(ep => episodeIsBusy(ep)))
const hasProducingEpisode = computed(() => episodes.value.some(ep => episodeHasProducingVideoRun(ep)))
const targetEpisodeCount = computed(() => Math.max(0, Number(series.value?.total_episodes || 0)))
const persistedEpisodeTargetReached = computed(() => episodes.value.length >= targetEpisodeCount.value)
const hasMissingEpisodePlaceholders = computed(() => targetEpisodeCount.value > episodes.value.length)
const incompleteTextEpisode = computed(() => episodes.value.find(ep => (
  finishedEpisodeStatuses.has(ep.status)
  && !episodeIsBusy(ep)
  && !episodeTextReady(ep)
)) || null)
const allPersistedEpisodesFinished = computed(() => (
  episodes.value.length > 0
  && persistedEpisodeTargetReached.value
  && episodes.value.every(ep => finishedEpisodeStatuses.has(ep.status) && episodeTextReady(ep) && !episodeHasActiveVideoRun(ep))
))
const styleLockInProgress = computed(() => styleLocking.value || styleLock.value?.status === 'locking')
const activeStoryPlanningStatuses = new Set(['planning', 'queued', 'running'])
const terminalStoryPlanningStatuses = new Set(['completed', 'fallback', 'failed'])
const closedStoryPlanningStatuses = new Set(['completed', 'fallback'])
const storyPlanningState = computed(() => {
  const storyBible = series.value?.story_bible_json || {}
  const state = storyBible.story_planning || {}
  return state && typeof state === 'object' ? state : {}
})
const storyPlanningStatus = computed(() => String(storyPlanningState.value.status || '').toLowerCase())
const storyPlanningInProgress = computed(() => storyPlanning.value || activeStoryPlanningStatuses.has(storyPlanningStatus.value))
const storyPlanningClosed = computed(() => closedStoryPlanningStatuses.has(storyPlanningStatus.value))
const storyPlanButtonDisabled = computed(() => storyPlanningInProgress.value || storyPlanningClosed.value)
const storyPlanButtonText = computed(() => {
  if (storyPlanningInProgress.value) return '故事规划中...'
  if (storyPlanningClosed.value) return '故事规划已完成'
  return '生成整季故事规划'
})
const pipelineStartDisabled = computed(() => pipelineStarting.value || (!runnableEpisode.value && !activeProductionRoute.value && !hasMissingEpisodePlaceholders.value && !incompleteTextEpisode.value))
const pipelineButtonText = computed(() => {
  if (pipelineStarting.value) return '启动中...'
  if (canContinueActiveProduction.value) return hasProducingEpisode.value ? '剧集生产中，打开监控' : '继续生产计划'
  if (hasProducingEpisode.value) return '剧集生产中'
  if (hasBusyEpisode.value) return '生产计划已创建'
  if (hasMissingEpisodePlaceholders.value && !runnableEpisode.value) return '补齐剧集占位'
  if (!runnableEpisode.value && incompleteTextEpisode.value) return `补齐第 ${incompleteTextEpisode.value.episode_number} 集剧本/分镜`
  if (!episodes.value.length) return '没有可启动剧集'
  if (!runnableEpisode.value) return allPersistedEpisodesFinished.value ? '全部剧集已完成' : '没有可启动剧集'
  return `生成第 ${runnableEpisode.value.episode_number} 集`
})
const storyPlanEpisodeCount = computed(() => new Set(
  aiTextArtifacts.value
    .filter(item => item?.artifact_type === 'episode_outline' && item.status === 'approved')
    .map(item => item.episode_id)
    .filter(Boolean)
).size)
const storyPlanSeriesArtifact = computed(() => latestSeriesArtifact('series_story_plan'))
const storyPlanSourceText = computed(() => {
  const artifact = storyPlanSeriesArtifact.value
  if (!artifact) return ''
  const trace = artifact.model_trace_json || {}
  if (trace.stage_status === 'fallback') return '系统回退规划'
  if (trace.expert_id === 'story_generator') return '故事生成专家'
  if (artifact.source_type === 'ai' || artifact.source_type === 'ai_story_plan') return 'AI 故事规划'
  return artifact.source_type || '故事规划已生成'
})
const storyPlanSourceClass = computed(() => storyPlanSourceText.value.includes('回退') ? 'text-amber-300' : 'text-cyan-300')
async function load() {
  loading.value = true; error.value = ''
  try {
    const { data } = await getSeries(route.params.id)
    if (data.ok) { series.value = data.series; episodes.value = data.episodes || [] } else throw new Error('Series not found')
    const [runsResp, styleResp] = await Promise.all([
      listRuns(route.params.id, { silent: true }).catch(() => ({ data: { ok: false, runs: [] } })),
      getStyleLock(route.params.id, { silent: true }).catch(() => ({ data: null })),
    ])
    runs.value = runsResp.data.ok ? runsResp.data.runs : []
    styleLock.value = styleResp.data
    if (expandedEpisodeId.value && !episodes.value.some(ep => ep.id === expandedEpisodeId.value)) {
      expandedEpisodeId.value = ''
    }
    refreshEpisodeTextArtifacts()
    applyStyleLockReferenceProgress(styleLock.value)
    scheduleStyleLockPoll()
    scheduleStoryPlanPoll()
  } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false }
  await maybeAutostartProduction()
}
function nextEpisode() {
  return runnableEpisode.value
}
function beginEditSeries() {
  Object.assign(seriesForm, {
    title: series.value?.title || '',
    logline: series.value?.logline || '',
    genre: series.value?.genre || '',
    target_duration: series.value?.target_duration || 60,
    mode: series.value?.mode || 'step_by_step',
    pilot_first: series.value?.pilot_first ?? true,
  })
  saveError.value = ''
  editingSeries.value = true
}
function errorMessage(e, fallback) {
  const detail = e.response?.data?.detail
  return detail?.message || detail || e.message || fallback
}
function isManagedImagePath(path) {
  return MANAGED_IMAGE_PREFIXES.some((prefix) => String(path || '').startsWith(prefix))
}
function tosSignedUrlExpired(value) {
  const trimmed = String(value || '').trim()
  if (!trimmed) return false
  let parsed
  try {
    parsed = new URL(trimmed, window.location.origin)
  } catch {
    return false
  }
  const date = parsed.searchParams.get('X-Tos-Date') || parsed.searchParams.get('x-tos-date')
  const expires = Number(parsed.searchParams.get('X-Tos-Expires') || parsed.searchParams.get('x-tos-expires'))
  const match = String(date || '').match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/)
  if (!match || !Number.isFinite(expires)) return false
  const [, year, month, day, hour, minute, second] = match
  const issuedAt = Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second))
  return Date.now() >= issuedAt + expires * 1000
}
function safeReferenceUrl(value) {
  if (typeof value !== 'string') return ''
  const trimmed = value.trim()
  if (!trimmed || trimmed.startsWith('//') || tosSignedUrlExpired(trimmed)) return ''
  if (isManagedImagePath(trimmed)) return trimmed
  try {
    const parsed = new URL(trimmed, window.location.origin)
    if (isManagedImagePath(parsed.pathname) && (parsed.origin === window.location.origin || LOOPBACK_HOSTS.has(parsed.hostname))) {
      return `${parsed.pathname}${parsed.search}${parsed.hash}`
    }
    return ['http:', 'https:'].includes(parsed.protocol) ? trimmed : ''
  } catch {
    return ''
  }
}
function linkedReferences(item, slotDefs) {
  return slotDefs
    .map((slot) => ({ ...slot, url: item?.[slot.key] || '', src: safeReferenceUrl(item?.[slot.key]) }))
    .filter((slot) => slot.src)
}
function linkedCharacterReferences(character) {
  return linkedReferences(character, CHARACTER_REFERENCE_SLOT_DEFS)
}
function linkedSceneReferences(scene) {
  return linkedReferences(scene, SCENE_REFERENCE_SLOT_DEFS)
}
function hasRawReference(item, slotDefs) {
  return slotDefs.some((slot) => Boolean(String(item?.[slot.key] || '').trim()))
}
function validProgressSlot(assetType, slot) {
  if (assetType === 'character') return CHARACTER_REFERENCE_SLOT_KEYS.has(slot)
  if (assetType === 'scene') return SCENE_REFERENCE_SLOT_KEYS.has(slot)
  return false
}
function progressReferencePatch(item) {
  const patch = {
    status: item.status,
    url: item.url,
  }
  if (item.source) patch.source = item.source
  if (item.error) patch.error = item.error
  if (item.updated_at) patch.updated_at = item.updated_at
  return patch
}
async function toggleEpisodeText(episodeId) {
  expandedEpisodeId.value = expandedEpisodeId.value === episodeId ? '' : episodeId
  if (expandedEpisodeId.value) {
    const ep = episodes.value.find(item => item.id === expandedEpisodeId.value)
    if (ep) await loadStoryboardImages(ep)
  }
}
async function refreshEpisodeTextArtifacts() {
  try {
    const { data } = await listAITextArtifacts({ series_id: route.params.id }, { silent: true })
    aiTextArtifacts.value = data?.ok ? data.artifacts || [] : []
    aiTextArtifactsError.value = ''
  } catch (e) {
    aiTextArtifacts.value = []
    aiTextArtifactsError.value = errorMessage(e, 'AI 文本加载失败')
  }
}
function isNonEmptyObject(value) {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length)
}
function isNonEmptyArray(value) {
  return Array.isArray(value) && value.length > 0
}
function artifactTimestamp(artifact) {
  return Date.parse(artifact?.approved_at || artifact?.created_at || '') || 0
}
function latestEpisodeArtifact(ep, artifactType) {
  return [...aiTextArtifacts.value]
    .filter(item => item?.episode_id === ep.id && item.artifact_type === artifactType && item.status === 'approved')
    .sort((a, b) => artifactTimestamp(b) - artifactTimestamp(a) || Number(b.version || 0) - Number(a.version || 0))[0] || null
}
function latestSeriesArtifact(artifactType) {
  return [...aiTextArtifacts.value]
    .filter(item => item?.target_type === 'series' && item.artifact_type === artifactType && item.status === 'approved')
    .sort((a, b) => artifactTimestamp(b) - artifactTimestamp(a) || Number(b.version || 0) - Number(a.version || 0))[0] || null
}
function artifactContent(artifact) {
  if (!artifact) return null
  if (isNonEmptyObject(artifact.content_json) || isNonEmptyArray(artifact.content_json)) return artifact.content_json
  return artifact.content_text || null
}
function scriptSource(ep) {
  return artifactContent(latestEpisodeArtifact(ep, 'episode_script')) || (isNonEmptyObject(ep?.script_json) ? ep.script_json : null)
}
function storyboardSource(ep) {
  return artifactContent(latestEpisodeArtifact(ep, 'storyboard')) || (isNonEmptyObject(ep?.storyboard_json) ? ep.storyboard_json : null)
}
function outlineSource(ep) {
  return artifactContent(latestEpisodeArtifact(ep, 'episode_outline'))
}
function formatContent(value) {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(formatContent).filter(Boolean).join('\n')
  if (typeof value !== 'object') return String(value)
  return JSON.stringify(value, null, 2)
}
function episodeScriptText(ep) {
  return formatContent(scriptSource(ep))
}
function episodeOutlineText(ep) {
  return formatContent(outlineSource(ep))
}
function episodeAssetScope(ep) {
  return ep?.asset_scope && typeof ep.asset_scope === 'object' ? ep.asset_scope : {}
}
function episodeAssetCharacters(ep) {
  const scope = episodeAssetScope(ep)
  if (Array.isArray(scope.characters) && scope.characters.length) return scope.characters
  return Array.isArray(scope.character_ids) ? scope.character_ids.map(id => ({ id, name: id, source: 'existing' })) : []
}
function episodeAssetScenes(ep) {
  const scope = episodeAssetScope(ep)
  if (Array.isArray(scope.scenes) && scope.scenes.length) return scope.scenes
  return Array.isArray(scope.scene_ids) ? scope.scene_ids.map(id => ({ id, name: id, source: 'existing' })) : []
}
function episodeAssetMissing(ep) {
  return !episodeAssetCharacters(ep).length || !episodeAssetScenes(ep).length
}
function episodeGeneratedAssets(ep) {
  const generated = []
  for (const item of [...episodeAssetCharacters(ep), ...episodeAssetScenes(ep)]) {
    if (item?.source === 'generated') generated.push(item.name || item.id)
  }
  return [...new Set(generated)]
}
function storyboardFrames(ep) {
  const storyboard = storyboardSource(ep)
  return Array.isArray(storyboard?.frames) ? storyboard.frames : []
}
function storyboardFrameIdentity(frame, index) {
  return frame?.frame_id || frame?.shot_id || frame?.id || `frame-${String(index + 1).padStart(3, '0')}`
}
function storyboardImageForFrame(ep, frame, index) {
  const state = storyboardImageState.value[ep.id] || {}
  const frameId = storyboardFrameIdentity(frame, index)
  return state.frames_by_id?.[frameId] || null
}
function storyboardImageUrl(ep, frame, index) {
  const item = storyboardImageForFrame(ep, frame, index)
  return safeReferenceUrl(item?.asset?.thumbnail_url) || safeReferenceUrl(item?.asset?.url)
}
function storyboardImageStatusLabel(status) {
  return {
    approved: '已通过',
    pending: '待审',
    running: '生成中',
    blocked: '已阻断',
    missing: '未生成',
  }[status || 'missing'] || '未生成'
}
function storyboardImageStatusClass(status) {
  if (status === 'approved') return 'text-emerald-300'
  if (status === 'pending' || status === 'running') return 'text-amber-300'
  if (status === 'blocked') return 'text-rose-300'
  return 'text-slate-500'
}
async function loadStoryboardImages(ep) {
  if (!ep?.id || !series.value?.id) return
  try {
    const { data } = await getStoryboardImageState(ep.id, episodeStoryboardImageParams(ep))
    storyboardImageState.value = {
      ...storyboardImageState.value,
      [ep.id]: data?.ok ? data : { frames: [], frames_by_id: {}, summary: {} },
    }
    storyboardImageErrors[ep.id] = ''
  } catch (e) {
    storyboardImageErrors[ep.id] = errorMessage(e, '分镜图状态加载失败')
  }
}
async function generateMissingFrameImages(ep) {
  if (!ep?.id || !series.value?.id || storyboardImageBusy[ep.id] === 'batch') return
  storyboardImageBusy[ep.id] = 'batch'
  try {
    await createMissingStoryboardImageTasks(ep.id, episodeStoryboardImageParams(ep))
    await loadStoryboardImages(ep)
  } catch (e) {
    storyboardImageErrors[ep.id] = errorMessage(e, '分镜图生成失败')
  } finally {
    delete storyboardImageBusy[ep.id]
  }
}
async function generateFrameImage(ep, frame, index) {
  const frameId = storyboardFrameIdentity(frame, index)
  const busyKey = `${ep.id}:${frameId}`
  if (!ep?.id || !series.value?.id || storyboardImageBusy[busyKey] === 'single') return
  storyboardImageBusy[busyKey] = 'single'
  try {
    await createStoryboardFrameImageTask(ep.id, frameId, episodeStoryboardImageParams(ep))
    await loadStoryboardImages(ep)
  } catch (e) {
    storyboardImageErrors[ep.id] = errorMessage(e, '分镜图生成失败')
  } finally {
    delete storyboardImageBusy[busyKey]
  }
}
async function generateScriptForEpisode(ep) {
  if (!ep?.id || !series.value?.id || episodeScriptGenerating[ep.id]) return
  episodeScriptGenerating[ep.id] = true
  episodeScriptErrors[ep.id] = ''
  try {
    await generateEpisodeScript(series.value.id, ep.id, {
      target_duration_seconds: Number(series.value?.target_duration || ep.duration_seconds || 60),
    })
    await load()
    await refreshEpisodeTextArtifacts()
  } catch (e) {
    episodeScriptErrors[ep.id] = errorMessage(e, '剧本生成失败')
  } finally {
    delete episodeScriptGenerating[ep.id]
  }
}
function storyboardFrameCount(ep) {
  return storyboardFrames(ep).length
}
function episodeStoryboardText(ep) {
  return formatContent(storyboardSource(ep))
}
function hasEpisodeScript(ep) {
  return Boolean(episodeScriptText(ep))
}
function episodeTextReady(ep) {
  return hasEpisodeScript(ep) && storyboardFrameCount(ep) > 0
}
function applyStyleLockReferenceProgress(lock) {
  if (!series.value || !Array.isArray(lock?.reference_progress)) return
  const characters = Array.isArray(series.value.characters) ? [...series.value.characters] : []
  const scenes = Array.isArray(series.value.scenes) ? [...series.value.scenes] : []
  let changed = false

  for (const item of lock.reference_progress) {
    const assetType = item?.asset_type
    const assetId = item?.asset_id
    const slot = item?.slot
    if (item?.status !== 'ready' || !assetId || !validProgressSlot(assetType, slot) || !safeReferenceUrl(item.url)) {
      continue
    }
    const collection = assetType === 'character' ? characters : scenes
    const index = collection.findIndex((entry) => entry?.id === assetId)
    if (index === -1) continue

    const current = collection[index] || {}
    const metaJson = { ...(current.meta_json || {}) }
    const referenceGeneration = { ...(metaJson.reference_generation || {}) }
    referenceGeneration[slot] = {
      ...(referenceGeneration[slot] || {}),
      ...progressReferencePatch(item),
    }
    collection[index] = {
      ...current,
      [slot]: item.url,
      meta_json: {
        ...metaJson,
        reference_generation: referenceGeneration,
      },
    }
    changed = true
  }

  if (changed) {
    series.value = {
      ...series.value,
      characters,
      scenes,
    }
  }
}
async function saveSeries() {
  savingSeries.value = true; saveError.value = ''
  try {
    await updateSeries(route.params.id, { ...seriesForm })
    editingSeries.value = false
    await load()
  } catch (e) {
    saveError.value = errorMessage(e, '保存系列失败')
  } finally { savingSeries.value = false }
}
async function removeCharacter(characterId) {
  unlinkErrors.character = ''
  try {
    await unlinkCharacter(route.params.id, characterId)
    await load()
  } catch (e) {
    unlinkErrors.character = errorMessage(e, '取消角色关联失败')
  }
}
async function removeScene(sceneId) {
  unlinkErrors.scene = ''
  try {
    await unlinkScene(route.params.id, sceneId)
    await load()
  } catch (e) {
    unlinkErrors.scene = errorMessage(e, '取消场景关联失败')
  }
}
async function removeSeries() {
  if (deletingSeries.value) return
  deletingSeries.value = true; deleteError.value = ''; deleteResult.value = ''
  try {
    const { data } = await deleteSeries(route.params.id)
    const action = data?.action || data?.result?.action || 'completed'
    deleteResult.value = `后端处理结果：${action}`
    deleteDialogOpen.value = false
    if (action === 'deleted') router.push('/series')
    else await load()
  } catch (e) {
    deleteError.value = errorMessage(e, '安全归档失败')
  } finally { deletingSeries.value = false }
}
async function generateStoryPlan() {
  if (storyPlanButtonDisabled.value) return
  storyPlanning.value = true
  storyPlanError.value = ''
  try {
    const { data } = await generateSeriesStoryPlan(route.params.id)
    storyPlanResult.value = data
    if (data?.story_planning && series.value) {
      series.value = {
        ...series.value,
        story_bible_json: {
          ...(series.value.story_bible_json || {}),
          story_planning: data.story_planning,
        },
      }
    }
    await load()
    await refreshEpisodeTextArtifacts()
  } catch (e) {
    storyPlanError.value = errorMessage(e, '故事规划生成失败')
  } finally {
    storyPlanning.value = false
  }
}
async function lockStyle(rethrow = false) {
  if (styleLockInProgress.value) return
  const shouldRethrow = rethrow === true
  styleLocking.value = true; error.value = ''
  try {
    const { data } = await lockSeriesStyle(route.params.id)
    const lock = data.story_bible?.style_lock || {}
    styleLock.value = {
      ...data,
      locked: Boolean(lock.locked),
      status: data.status || lock.status || 'locking',
      version: lock.version || data.version || 1,
    }
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '风格锁定失败'
    if (shouldRethrow) throw e
  } finally { styleLocking.value = false }
}
async function refreshStyleLock() {
  try {
    const { data } = await getStyleLock(route.params.id)
    styleLock.value = data
    applyStyleLockReferenceProgress(data)
    if (data?.status !== 'locking') await load()
  } catch {
    scheduleStyleLockPoll()
    return
  }
  scheduleStyleLockPoll()
}
function scheduleStyleLockPoll() {
  if (styleLockPollTimer.value) {
    clearTimeout(styleLockPollTimer.value)
    styleLockPollTimer.value = null
  }
  if (styleLock.value?.status === 'locking') {
    styleLockPollTimer.value = setTimeout(refreshStyleLock, 5000)
  }
}
async function refreshStoryPlan() {
  try {
    await load()
    if (terminalStoryPlanningStatuses.has(storyPlanningStatus.value)) {
      await refreshEpisodeTextArtifacts()
    }
  } catch {
    scheduleStoryPlanPoll()
  }
}
function scheduleStoryPlanPoll() {
  if (storyPlanPollTimer.value) {
    clearTimeout(storyPlanPollTimer.value)
    storyPlanPollTimer.value = null
  }
  if (activeStoryPlanningStatuses.has(storyPlanningStatus.value)) {
    storyPlanPollTimer.value = setTimeout(refreshStoryPlan, 5000)
  }
}
onBeforeUnmount(() => {
  if (styleLockPollTimer.value) clearTimeout(styleLockPollTimer.value)
  if (storyPlanPollTimer.value) clearTimeout(storyPlanPollTimer.value)
})
async function startPipelineRun() {
  if (!runnableEpisode.value && activeProductionRoute.value) {
    router.push(activeProductionRoute.value)
    return
  }
  if (!runnableEpisode.value && hasMissingEpisodePlaceholders.value) {
    pipelineStarting.value = true; error.value = ''
    try {
      await ensureSeriesEpisodes(route.params.id)
      await load()
    } catch (e) {
      const detail = e.response?.data?.detail
      error.value = detail?.message || detail || e.message || '补齐剧集失败'
    } finally { pipelineStarting.value = false }
    return
  }
  if (!runnableEpisode.value && incompleteTextEpisode.value) {
    pipelineStarting.value = true; error.value = ''
    const ep = incompleteTextEpisode.value
    try {
      await generateScriptForEpisode(ep)
      if (episodeScriptErrors[ep.id]) error.value = episodeScriptErrors[ep.id]
    } finally { pipelineStarting.value = false }
    return
  }
  pipelineStarting.value = true; error.value = ''
  try {
    if (!styleLock.value?.locked) await lockStyle(true)
    if (!styleLock.value?.locked) {
      throw new Error('风格锁定正在后台执行，请等待完成后再启动生产')
    }
    const ep = nextEpisode()
    if (!ep) throw new Error('没有可启动的剧集')
    const { data } = await startEpisodeProduction({
      series_id: route.params.id,
      episode_id: ep.id,
      target_duration_seconds: series.value?.target_duration,
      autostart_images: series.value?.mode === 'fully_automatic',
    })
    if (!data?.route) throw new Error('Production run was not created')
    router.push(data.route)
  } catch (e) {
    const detail = e.response?.data?.detail
    error.value = detail?.message || detail || e.message || '启动失败'
  } finally { pipelineStarting.value = false }
}
async function maybeAutostartProduction() {
  if (!autostartRequested.value || autostartRunning.value || pipelineStarting.value) return
  if (!series.value) return
  if (series.value.mode !== 'fully_automatic') {
    autostartRequested.value = false
    return
  }
  if (!runnableEpisode.value) {
    autostartRequested.value = false
    return
  }
  if (styleLock.value?.status === 'locking') return
  autostartRunning.value = true
  try {
    await startPipelineRun()
    if (!error.value) autostartRequested.value = false
  } finally {
    autostartRunning.value = false
  }
}
async function autoGenerate() {
  autoGenerating.value = true; autoGenResult.value = null; error.value = ''
  try {
    autoGenStep.value = 'AI 正在分析故事，生成角色档案...'
    const { data } = await autoGenerateAssets(route.params.id)
    if (data.ok) {
      autoGenResult.value = data
      autoGenStep.value = ''
      await load()
    } else throw new Error('生成失败')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'AI 生成失败'
    autoGenerating.value = false
  } finally { autoGenerating.value = false }
}
function epStatusClass(s) { return { pending: 'bg-gray-800 text-slate-400', rendering: 'bg-yellow-900/40 text-yellow-400', done: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400' }[s] || 'bg-gray-800 text-slate-400' }
function runStatusClass(s) { return { running: 'bg-sky-900/40 text-sky-400', completed: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400', pending: 'bg-gray-800 text-slate-400' }[s] || 'bg-gray-800 text-slate-400' }
onMounted(load)
</script>
