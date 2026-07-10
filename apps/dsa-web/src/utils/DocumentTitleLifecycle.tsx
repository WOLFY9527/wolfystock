import type React from 'react';
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import type { UiLanguage } from '../i18n/core';
import { getDocumentTitle } from './documentTitle';

export const DocumentTitleLifecycle: React.FC<{ language: UiLanguage }> = ({ language }) => {
  const location = useLocation();
  const title = getDocumentTitle(location.pathname, language);

  useEffect(() => {
    document.title = title;
  }, [title]);

  return null;
};
