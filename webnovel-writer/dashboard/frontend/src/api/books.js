import { requestJSON } from './http.js'

/**
 * Initialize a new book project.
 *
 * @param {object} params – All init_project keyword parameters.
 * @param {string} params.title – Book title (required).
 * @param {string} params.genre – Genre string (required).
 * @param {string} params.project_dir – Project directory (required).
 * @returns {Promise<{project_root: string, book_id: string, title: string}>}
 */
export async function initBook(params) {
    return requestJSON('/api/books/init', {
        method: 'POST',
        body: params,
    })
}
