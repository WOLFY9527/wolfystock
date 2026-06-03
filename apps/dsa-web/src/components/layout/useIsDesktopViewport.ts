import { useEffect, useState } from 'react';

function getIsDesktopViewport(): boolean {
  if (typeof window === 'undefined') {
    return true;
  }
  return window.innerWidth >= 1024;
}

export function useIsDesktopViewport(): boolean {
  const [isDesktop, setIsDesktop] = useState(getIsDesktopViewport);

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(getIsDesktopViewport());
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return isDesktop;
}
