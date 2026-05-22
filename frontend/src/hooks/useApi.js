import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api';

/**
 * Custom hook for GET requests via react-query.
 * @param {string|string[]} queryKey - Unique key for caching.
 * @param {string} url - API endpoint (relative to /api).
 * @param {object} [options] - Additional react-query options.
 */
export function useApiQuery(queryKey, url, options = {}) {
  return useQuery({
    queryKey: Array.isArray(queryKey) ? queryKey : [queryKey],
    queryFn: async () => {
      const { data } = await apiClient.get(url);
      return data;
    },
    ...options,
  });
}

/**
 * Custom hook for mutations (POST/PUT/PATCH/DELETE) via react-query.
 * @param {string} url - API endpoint (relative to /api).
 * @param {'post'|'put'|'patch'|'delete'} [method='post'] - HTTP method.
 * @param {object} [options] - Additional react-query mutation options.
 */
export function useApiMutation(url, method = 'post', options = {}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body) => {
      const { data } = await apiClient[method](url, body);
      return data;
    },
    onSuccess: () => {
      // Optionally invalidate queries after a successful mutation
      if (options.invalidateKeys) {
        options.invalidateKeys.forEach((key) =>
          queryClient.invalidateQueries({ queryKey: Array.isArray(key) ? key : [key] })
        );
      }
    },
    ...options,
  });
}
