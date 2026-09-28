import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useTranslate } from "../../../i18n/useTranslate";
import { defaultClient, errorText, type ApiClient } from "../../../services/api/client";
import { deleteTask, listTasks, retryTask } from "../../../services/api/tasks";
import type { TaskStatus } from "../../../services/api/tasks";

const TASKS_LIST_QUERY_KEY = ["tasks", "list"] as const;
const TASK_POLL_INTERVAL = 2000;

export function useTasks(statusFilter: TaskStatus | null = null, client: ApiClient = defaultClient) {
  const t = useTranslate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const query = useQuery({
    queryKey: [...TASKS_LIST_QUERY_KEY, statusFilter, page, pageSize] as const,
    queryFn: async () => {
      const response = await listTasks(statusFilter, page, pageSize, client);
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

  const remove = useMutation({
    mutationFn: (taskId: string) => deleteTask(taskId, client),
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
    removeTask: remove,
  };
}
