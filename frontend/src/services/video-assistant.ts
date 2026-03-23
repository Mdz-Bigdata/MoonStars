import axios from 'axios';

const API_BASE = '/api/video-note';

export interface VideoNoteConfig {
    video_url: string;
    platform: string;
    quality: 'fast' | 'medium' | 'slow';
    screenshot: boolean;
    link: boolean;
    model_name: string;
    provider_id: string;
    style: string;
    format: string[];
    video_understanding?: boolean;
    video_interval?: number;
    grid_size?: [number, number];
    extras?: string;
}

export const generateVideoNote = async (config: VideoNoteConfig) => {
    const response = await axios.post(`${API_BASE}/generate_note`, config);
    return response.data;
};

export const getTaskStatus = async (taskId: string) => {
    const response = await axios.get(`${API_BASE}/task_status/${taskId}`);
    return response.data;
};

export const fetchVideoModels = async () => {
    const response = await axios.get('/api/video-model/model_list');
    return response.data;
};

export const fetchVideoProviders = async () => {
    const response = await axios.get('/api/video-provider/provider_list');
    return response.data;
};

export const fetchVideoHistory = async () => {
    const response = await axios.get(`${API_BASE}/history`);
    return response.data;
};

export const deleteVideoTask = async (taskId: string) => {
    const response = await axios.post(`${API_BASE}/delete_task`, {
        video_id: taskId,
        platform: 'all'
    });
    return response.data;
};

// Component structure objects
export const videoModelApi = {
    getModelListV2: async (providerId: string) => {
        const response = await axios.get(`/api/video-model/model_list/${providerId}`);
        return response.data;
    }
};

export const videoProviderApi = {
    testConnectivity: async (config: any) => {
        const response = await axios.post('/api/video-provider/test_connection', config);
        return response.data;
    }
};

export const videoConfigApi = {
    getAll: async () => {
        const response = await axios.get('/api/video-config/get_all');
        return response.data;
    }
};
