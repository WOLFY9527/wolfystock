export function joinApiPath(basePath: string, path: string): string {
  const normalizedBasePath = basePath.replace(/\/+$/, '');
  const normalizedPath = path.replace(/^\/+/, '');

  if (!normalizedBasePath) {
    return normalizedPath ? `/${normalizedPath}` : '/';
  }

  if (!normalizedPath) {
    return normalizedBasePath || '/';
  }

  return `${normalizedBasePath}/${normalizedPath}`;
}

export function buildAbsoluteApiUrl(baseUrl: string, path: string): string {
  if (!baseUrl) {
    return path;
  }

  return joinApiPath(baseUrl, path);
}
