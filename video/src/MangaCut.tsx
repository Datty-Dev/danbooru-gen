import React from 'react';
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Img,
  staticFile,
} from 'remotion';

const FRAMES_PER_PANEL = 45;
const TRANSITION_FRAMES = 8;

const panels = [
  staticFile('panels/panel1-training.png'),
  staticFile('panels/panel2-scream.png'),
  staticFile('panels/panel3-cliff.png'),
];

export const MangaCut: React.FC = () => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();

  const panelIndex = Math.min(
    Math.floor(frame / FRAMES_PER_PANEL),
    panels.length - 1
  );

  const panelFrame = frame - panelIndex * FRAMES_PER_PANEL;
  const isTransition = panelFrame < TRANSITION_FRAMES && panelIndex > 0;

  // Whip-pan: horizontal smear during transition
  const transitionProgress = isTransition
    ? interpolate(panelFrame, [0, TRANSITION_FRAMES], [0, 1], {
        extrapolateRight: 'clamp',
      })
    : 1;

  // Blur amount: sharp during transition, 0 otherwise
  const blurAmount = isTransition
    ? interpolate(panelFrame, [0, TRANSITION_FRAMES], [20, 0], {
        extrapolateRight: 'clamp',
      })
    : 0;

  // Horizontal slide offset for whip feel
  const slideX = isTransition
    ? interpolate(panelFrame, [0, TRANSITION_FRAMES], [-width * 0.3, 0], {
        extrapolateRight: 'clamp',
      })
    : 0;

  // Scale punch: slight zoom-in on impact
  const scale = isTransition
    ? interpolate(panelFrame, [0, TRANSITION_FRAMES], [1.08, 1], {
        extrapolateRight: 'clamp',
      })
    : 1;

  // Brightness flash on impact
  const brightness = isTransition
    ? interpolate(panelFrame, [0, 3], [1.4, 1], {
        extrapolateRight: 'clamp',
      })
    : 1;

  // Previous panel sliding out
  const prevSlideX = isTransition
    ? interpolate(panelFrame, [0, TRANSITION_FRAMES], [0, width * 0.5], {
        extrapolateRight: 'clamp',
      })
    : 0;

  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      {/* Previous panel sliding out */}
      {isTransition && (
        <AbsoluteFill
          style={{
            transform: `translateX(${prevSlideX}px)`,
            filter: `blur(${blurAmount}px)`,
          }}
        >
          <Img
            src={panels[panelIndex - 1]}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
            }}
          />
        </AbsoluteFill>
      )}

      {/* Current panel slamming in */}
      <AbsoluteFill
        style={{
          transform: `translateX(${slideX}px) scale(${scale})`,
          filter: `blur(${blurAmount}px) brightness(${brightness})`,
        }}
      >
        <Img
          src={panels[panelIndex]}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        />
      </AbsoluteFill>

      {/* White flash on impact */}
      {isTransition && panelFrame < 3 && (
        <AbsoluteFill
          style={{
            backgroundColor: 'white',
            opacity: interpolate(panelFrame, [0, 3], [0.7, 0], {
              extrapolateRight: 'clamp',
            }),
          }}
        />
      )}

      {/* Cinematic letterbox bars */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '8%',
          backgroundColor: 'black',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: '8%',
          backgroundColor: 'black',
        }}
      />
    </AbsoluteFill>
  );
};
