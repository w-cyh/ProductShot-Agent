export interface StudioDraftForm {
  product_name: string
  product_category: string
  core_selling_points: string
  target_audience: string
}

export interface StudioDraft {
  form: StudioDraftForm
  file?: Blob
  fileName?: string
  fileType?: string
  fileLastModified?: number
  updatedAt: number
}

const DATABASE_NAME = 'productshot-studio'
const STORE_NAME = 'drafts'
const DRAFT_KEY = 'new-project'

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = window.indexedDB.open(DATABASE_NAME, 1)
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) request.result.createObjectStore(STORE_NAME)
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('无法打开本地草稿'))
  })
}

async function withStore<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>) {
  const database = await openDatabase()
  try {
    return await new Promise<T>((resolve, reject) => {
      const request = action(database.transaction(STORE_NAME, mode).objectStore(STORE_NAME))
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error || new Error('本地草稿操作失败'))
    })
  } finally {
    database.close()
  }
}

export function loadStudioDraft() {
  return withStore<StudioDraft | undefined>('readonly', (store) => store.get(DRAFT_KEY))
}

export function saveStudioDraft(draft: StudioDraft) {
  return withStore<IDBValidKey>('readwrite', (store) => store.put(draft, DRAFT_KEY))
}

export function clearStudioDraft() {
  return withStore<undefined>('readwrite', (store) => store.delete(DRAFT_KEY))
}
