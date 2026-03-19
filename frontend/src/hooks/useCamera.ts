import { useRef, useState, useCallback, useEffect } from "react";

type FacingMode = "user" | "environment";

interface UseCameraOptions {
  facingMode?: FacingMode;
  width?: number;
  height?: number;
}

interface UseCameraReturn {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  stream: MediaStream | null;
  isReady: boolean;
  error: string | null;
  facingMode: FacingMode;
  startCamera: () => Promise<void>;
  stopCamera: () => void;
  capturePhoto: () => Blob | null;
  switchCamera: () => Promise<void>;
  hasPermission: boolean | null;
}

export function useCamera(options: UseCameraOptions = {}): UseCameraReturn {
  const {
    facingMode: initialFacingMode = "environment",
    width = 1920,
    height = 1080,
  } = options;

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [stream, setStream] = useState<MediaStream | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<FacingMode>(initialFacingMode);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setStream(null);
    setIsReady(false);
  }, []);

  const startCamera = useCallback(async () => {
    stopCamera();
    setError(null);

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode,
          width: { ideal: width },
          height: { ideal: height },
        },
        audio: false,
      });

      streamRef.current = mediaStream;
      setStream(mediaStream);
      setHasPermission(true);

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        await videoRef.current.play();
        setIsReady(true);
      }
    } catch (err) {
      if (err instanceof DOMException) {
        if (err.name === "NotAllowedError") {
          setHasPermission(false);
          setError("Camera access denied. Please enable camera permissions.");
        } else if (err.name === "NotFoundError") {
          setError("No camera found on this device.");
        } else if (err.name === "NotReadableError") {
          setError("Camera is in use by another application.");
        } else {
          setError(`Camera error: ${err.message}`);
        }
      } else {
        setError("Failed to access camera.");
      }
    }
  }, [facingMode, width, height, stopCamera]);

  const capturePhoto = useCallback((): Blob | null => {
    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (!video || !canvas || !isReady) {
      return null;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return null;
    }

    ctx.drawImage(video, 0, 0);

    // Convert canvas to blob synchronously via toDataURL, then convert
    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
    const byteString = atob(dataUrl.split(",")[1] ?? "");
    const mimeString = dataUrl.split(",")[0]?.split(":")[1]?.split(";")[0] ?? "image/jpeg";
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    return new Blob([ab], { type: mimeString });
  }, [isReady]);

  const switchCamera = useCallback(async () => {
    const newMode: FacingMode =
      facingMode === "environment" ? "user" : "environment";
    setFacingMode(newMode);
  }, [facingMode]);

  // Restart camera when facing mode changes
  useEffect(() => {
    if (stream) {
      void startCamera();
    }
    // Only trigger on facingMode change, not startCamera identity
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facingMode]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  return {
    videoRef,
    canvasRef,
    stream,
    isReady,
    error,
    facingMode,
    startCamera,
    stopCamera,
    capturePhoto,
    switchCamera,
    hasPermission,
  };
}
