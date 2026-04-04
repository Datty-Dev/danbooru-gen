import {registerRoot} from 'remotion';
import {MangaCut} from './MangaCut';

const FRAMES_PER_PANEL = 45;
const PANELS = 3;

registerRoot(() => {
  return {
    id: 'manga-cut',
    component: MangaCut,
    durationInFrames: FRAMES_PER_PANEL * PANELS, // 135 frames = 4.5s at 30fps
    fps: 30,
    width: 1080,
    height: 1920,
    defaultProps: {},
  };
});
