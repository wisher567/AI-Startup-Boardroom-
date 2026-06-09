import { useEffect, useRef } from 'react';
import Phaser from 'phaser';
import { BoardroomScene } from './BoardroomScene';

export default function GameWrapper({ onSceneReady }) {
  const containerRef = useRef(null);
  const gameRef = useRef(null);
  const readyCalled = useRef(false);

  useEffect(() => {
    const config = {
      type: Phaser.AUTO,
      width: 800,
      height: 500,
      parent: containerRef.current,
      backgroundColor: '#1a1a2e',
      scene: BoardroomScene,
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
      },
      pixelArt: true,
      roundPixels: true,
    };

    gameRef.current = new Phaser.Game(config);

    // Poll for scene availability (Phaser creates scenes asynchronously)
    const checkScene = setInterval(() => {
      if (readyCalled.current) {
        clearInterval(checkScene);
        return;
      }
      const scene = gameRef.current?.scene?.getScene('Boardroom');
      if (scene && scene.scene.isActive()) {
        readyCalled.current = true;
        clearInterval(checkScene);
        if (onSceneReady) onSceneReady(scene);
      }
    }, 100);

    return () => {
      clearInterval(checkScene);
      gameRef.current?.destroy(true);
      gameRef.current = null;
      readyCalled.current = false;
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden border border-gray-800"
      style={{ maxWidth: 800, aspectRatio: '800 / 500' }}
    />
  );
}
