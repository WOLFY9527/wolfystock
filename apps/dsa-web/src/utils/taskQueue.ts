import type { TaskInfo } from '../types/analysis';

export const MAX_RECENT_TASKS = 12;

function getTaskStatusWeight(task: TaskInfo): number {
  if (task.status === 'processing') {
    return 3;
  }
  if (task.status === 'pending') {
    return 2;
  }
  if (task.status === 'failed') {
    return 1;
  }
  return 0;
}

function getTaskActivityTimestamp(task: TaskInfo): number {
  return Date.parse(task.updatedAt || task.completedAt || task.startedAt || task.createdAt || '');
}

export function sortTasksByPriority(tasks: TaskInfo[]): TaskInfo[] {
  return tasks
    .slice()
    .sort((left, right) => {
      const statusDiff = getTaskStatusWeight(right) - getTaskStatusWeight(left);
      if (statusDiff !== 0) {
        return statusDiff;
      }

      return getTaskActivityTimestamp(right) - getTaskActivityTimestamp(left);
    })
    .slice(0, MAX_RECENT_TASKS);
}
