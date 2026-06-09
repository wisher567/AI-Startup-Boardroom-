import { useEffect, useRef } from 'react';
import { createBoardroomGame } from '../game/BoardroomGame';

export function PhaserCanvas({ registerPhaserEmitter }) {
  const containerRef = useRef(null);
  const gameRef      = useRef(null);

  useEffect(() => {
    if (!containerRef.current || gameRef.current) return;

    gameRef.current = createBoardroomGame(containerRef.current, registerPhaserEmitter);

    return () => {
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, [registerPhaserEmitter]);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', aspectRatio: '860/530' }}
      className="rounded-lg overflow-hidden border border-white/10"
    />
  );
}
