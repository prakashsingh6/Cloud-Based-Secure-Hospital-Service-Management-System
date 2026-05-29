import { useState, useEffect, useCallback } from 'react';
import type { ServiceRequest, MedicalReport, IoTRoom, DashboardStats, ServiceType, RequestStatus } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

const getToken = () => localStorage.getItem('zetatech_token');

const apiFetch = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail ?? 'Request failed');
  }

  return response.json();
};

export const useData = () => {
  const [requests, setRequests] = useState<ServiceRequest[]>([]);
  const [reports, setReports] = useState<MedicalReport[]>([]);
  const [rooms, setRooms] = useState<IoTRoom[]>([]);
  const [stats, setStats] = useState<DashboardStats>({
    totalRequests: 0,
    pendingRequests: 0,
    approvedRequests: 0,
    rejectedRequests: 0,
    totalUsers: 0,
    activeRooms: 0
  });
  const [isInitialized, setIsInitialized] = useState(false);

  const refreshAll = useCallback(async () => {
    const [allRequests, allRooms, dashboardStats] = await Promise.all([
      apiFetch<ServiceRequest[]>('/requests'),
      apiFetch<IoTRoom[]>('/rooms'),
      apiFetch<DashboardStats>('/stats')
    ]);

    setRequests(allRequests);
    setRooms(allRooms);
    setStats(dashboardStats);
  }, []);

  useEffect(() => {
    refreshAll()
      .catch(() => {
        setRequests([]);
        setRooms([]);
      })
      .finally(() => setIsInitialized(true));
  }, [refreshAll]);

  const createRequest = useCallback(async (userId: string, userEmail: string, serviceType: ServiceType): Promise<ServiceRequest> => {
    const newRequest = await apiFetch<ServiceRequest>('/requests', {
      method: 'POST',
      body: JSON.stringify({ userId, userEmail, serviceType })
    });
    await refreshAll();
    return newRequest;
  }, [refreshAll]);

  const updateRequestStatus = useCallback(async (requestId: string, status: RequestStatus, reason?: string) => {
    await apiFetch<ServiceRequest>(`/requests/${requestId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, reason })
    });
    await refreshAll();
  }, [refreshAll]);

  const getUserRequests = useCallback(async (userId: string) => {
    const userRequests = await apiFetch<ServiceRequest[]>(`/users/${userId}/requests`);
    setRequests(prev => {
      const otherRequests = prev.filter(request => request.userId !== userId);
      return [...userRequests, ...otherRequests];
    });
    return userRequests;
  }, []);

  const getAllRequests = useCallback(async () => {
    const allRequests = await apiFetch<ServiceRequest[]>('/requests');
    setRequests(allRequests);
    return allRequests;
  }, []);

  const getUserReports = useCallback(async (userId: string) => {
    const userReports = await apiFetch<MedicalReport[]>(`/users/${userId}/reports`);
    setReports(userReports);
    return userReports;
  }, []);

  const createReport = useCallback(async (report: Omit<MedicalReport, 'id' | 'createdAt'>) => {
    const newReport = await apiFetch<MedicalReport>('/reports', {
      method: 'POST',
      body: JSON.stringify(report)
    });
    setReports(prev => [newReport, ...prev]);
    return newReport;
  }, []);

  const getAllRooms = useCallback(async () => {
    const allRooms = await apiFetch<IoTRoom[]>('/rooms');
    setRooms(allRooms);
    return allRooms;
  }, []);

  const updateRoomStatus = useCallback(async (roomId: string, status: 'available' | 'busy') => {
    const updatedRoom = await apiFetch<IoTRoom>(`/rooms/${roomId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status })
    });
    setRooms(prev => prev.map(room => room.roomId === roomId ? updatedRoom : room));
    return updatedRoom;
  }, []);

  const getDashboardStats = useCallback(async (): Promise<DashboardStats> => {
    const dashboardStats = await apiFetch<DashboardStats>('/stats');
    setStats(dashboardStats);
    return dashboardStats;
  }, []);

  return {
    requests,
    reports,
    rooms,
    stats,
    isInitialized,
    refreshAll,
    createRequest,
    updateRequestStatus,
    getUserRequests,
    getAllRequests,
    getUserReports,
    createReport,
    getAllRooms,
    updateRoomStatus,
    getDashboardStats
  };
};
