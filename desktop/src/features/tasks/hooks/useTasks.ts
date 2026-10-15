import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useTranslate } from "../../../i18n/useTranslate";
import { defaultClient, errorText, type ApiClient } from "../../../services/api/client";
import {
  cancelIncompleteTasks,
  cancelTask,
  continueCancelledTasks,
  deleteCompletedTasks,
  deleteTask,
  listTasks,
  retryTask,
} from "../../../services/api/tasks";

const TASKS_LIST_QUERY_KEY = ["tasks", "list"] as const;
const TASK_POLL_INTERVAL = 2000;

export function useTasks(client: ApiClient = defaultClient) {
  const t = useTranslate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const query = useQuery({
    queryKey: [...TASKS_LIST_QUERY_KEY, page, pageSize] as const,
    queryFn: async () => {
      const response = await listTasks(null, page, pageSize, client);
      if (response.status !== "success" || !response.data) {
        throw new Error(errorText(response.error) || t("tasks.loadFailed", "加载任务失败"));
      }
      return response.data;
    },
    refetchInterval: TASK_POLL_INTERVAL,
    refetchIntervalInBackground: false,
  });

  const retry = useMutation({
    mutationFn: (taskId: string) => retryTask(taskId, client),
    onSuccess: (response) => {
      if (response.status === "success") {
        void queryClient.invalidateQueries({ queryKey: TASKS_LIST_QUERY_KEY });
      }
      return response;
    },
  });

  const cancel = useMutation({
    mutationFn: (taskId: string) => cancelTask(taskId, client),
    onSuccess: (response) => {
      if (response.status === "success") {
        void queryClient.invalidateQueries({ queryKey: TASKS_LIST_QUERY_KEY });
      }
      return response;
    },
  });

  const remove = useMutation({
    mutationFn: (taskId: string) => deleteTask(taskId, client),
    onSuccess: (response) => {
      if (response.status === "success") {
        void queryClient.invalidateQueries({ queryKey: TASKS_LIST_QUERY_KEY });
      }
      return response;
    },
  });

  const cancelIncomplete = useMutation({
    mutationFn: () => cancelIncompleteTasks(client),
    onSuccess: (response) => {
      if (response.status === "success") {
        void queryClient.invalidateQueries({ queryKey: TASKS_LIST_QUERY_KEY });
      }
      return response;
    },
  });

  const continueCancelled = useMutation({
    mutationFn: () => continueCancelledTasks(client),
    onSuccess: (response) => {
      if (response.status === "success") {
        void queryClient.invalidateQueries({ queryKey: TASKS_LIST_QUERY_KEY });
      }
      return response;
    },
  });

  const deleteCompleted = useMutation({
    mutationFn: () => deleteCompletedTasks(client),
    onSuccess: (response) => {
      if (response.status === "success") {
        void queryClient.invalidateQueries({ queryKey: TASKS_LIST_QUERY_KEY });
      }
      return response;
    },
  });

  return {
    data: query.data,
    loading: query.isPending,
    error: query.error instanceof Error ? query.error.message : null,
    page,
    setPage,
    pageSize,
    reload: () => queryClient.invalidateQueries({ queryKey: TASKS_LIST_QUERY_KEY }),
    retryTask: retry,
    cancelTask: cancel,
    removeTask: remove,
    cancelIncompleteTasks: cancelIncomplete,
    continueCancelledTasks: continueCancelled,
    deleteCompletedTasks: deleteCompleted,
  };
}
