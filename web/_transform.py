import re, sys

PATH = "d:/devWorkspace/jsProjects/dy_auto/web/src/views/DMSequenceManagePage.vue"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# 1. Add getDMSequence to import
src = src.replace(
    "import { listDMSequences, createDMSequence, updateDMSequence, deleteDMSequence } from",
    "import { listDMSequences, createDMSequence, updateDMSequence, deleteDMSequence, getDMSequence } from"
)

# 2. Add AI refs after editingId ref
src = src.replace(
    "const editingId = ref(null)\n\nlet _savedFocusEl = null",
    "const editingId = ref(null)\n\n// AI generation\nconst aiDescription = ref('\nconst aiLinkUrl = ref('\nconst generating = ref(false)\nconst generateStatus = ref('\nconst generatingVariants = ref(false)\n\nlet _savedFocusEl = null"
)

# 3. Add AI field reset in resetForm
src = src.replace(
    "  editingId.value = null\n}",
    "  editingId.value = null\n  aiDescription.value = '\n  aiLinkUrl.value = '\n  generateStatus.value = '\n}"
)
