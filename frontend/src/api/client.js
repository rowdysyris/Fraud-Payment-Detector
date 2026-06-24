import axios from 'axios';
import { getApiErrorMessage } from '../utils/formatters';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

export async function getHealth() {
  try {
    const response = await api.get('/health');
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error));
  }
}

export async function analyzeTransactions(file, onUploadProgress) {
  if (!file) {
    throw new Error('Please select a CSV, XLS, or XLSX file.');
  }

  const validExtensions = ['csv', 'xls', 'xlsx'];
  const extension = file.name?.split('.').pop()?.toLowerCase();
  if (!validExtensions.includes(extension)) {
    throw new Error('Unsupported file type. Upload a CSV, XLS, or XLSX transaction dataset.');
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await api.post('/api/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress,
    });
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error));
  }
}

export function buildDownloadUrl(path) {
  if (!path) return '#';
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

export async function getTransactionDetail(jobId, transactionId) {
  if (!jobId) throw new Error('Missing job ID for transaction detail.');
  if (!transactionId) throw new Error('Missing transaction ID for transaction detail.');

  try {
    const response = await api.get(`/api/transaction-detail/${encodeURIComponent(jobId)}/${encodeURIComponent(transactionId)}`);
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error));
  }
}

export async function updateTransactionReviewStatus(jobId, transactionId, reviewStatus) {
  if (!jobId) throw new Error('Missing job ID for review update.');
  if (!transactionId) throw new Error('Missing transaction ID for review update.');
  if (!reviewStatus) throw new Error('Missing review status.');

  try {
    const response = await api.patch(
      `/api/transaction-review/${encodeURIComponent(jobId)}/${encodeURIComponent(transactionId)}`,
      { review_status: reviewStatus },
    );
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error));
  }
}
