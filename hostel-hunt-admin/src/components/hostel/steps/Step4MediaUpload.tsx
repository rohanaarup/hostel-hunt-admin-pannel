import React, { useCallback, useRef } from 'react';
import axios from 'axios';
import type { HostelEnrollmentState, MediaItem, MediaCategory } from '../../../types';

interface Props {
  data: HostelEnrollmentState;
  onChange: (key: keyof HostelEnrollmentState, value: unknown) => void;
}

function uid() { return Math.random().toString(36).slice(2, 10); }

const CATEGORY_CONFIG: { key: MediaCategory; label: string; icon: string; accept: string }[] = [
  { key: 'hostel', label: 'Hostel Images', icon: '🏨', accept: 'image/*' },
  { key: 'room', label: 'Room Images', icon: '🛏', accept: 'image/*' },
  { key: 'common_area', label: 'Common Area', icon: '🛋', accept: 'image/*' },
  { key: 'video', label: 'Videos', icon: '🎥', accept: 'video/*' },
];

export const Step4MediaUpload: React.FC<Props> = ({ data, onChange }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeCategory, setActiveCategory] = React.useState<MediaCategory>('hostel');
  const [dragOver, setDragOver] = React.useState(false);

  const media = data.media;

  const addFiles = useCallback((files: FileList, category: MediaCategory) => {
    const newItems: MediaItem[] = Array.from(files).map((file, i) => ({
      id: uid(),
      file,
      preview_url: URL.createObjectURL(file),
      category,
      upload_progress: 0,
      mime_type: file.type,
      file_name: file.name,
      order_index: media.filter(m => m.category === category).length + i,
    }));

    const updated = [...media, ...newItems];
    onChange('media', updated);

    // Get Cloudinary credentials from environment variables
    const cloudName = import.meta.env.VITE_CLOUDINARY_CLOUD_NAME;
    const uploadPreset = import.meta.env.VITE_CLOUDINARY_UPLOAD_PRESET;

    if (!cloudName || !uploadPreset) {
      alert("Cloudinary credentials are missing. Please add VITE_CLOUDINARY_CLOUD_NAME and VITE_CLOUDINARY_UPLOAD_PRESET to your .env file.");
      return;
    }

    newItems.forEach(item => {
      if (!item.file) return;

      const formData = new FormData();
      formData.append('file', item.file);
      formData.append('upload_preset', uploadPreset);

      const resourceType = item.mime_type.startsWith('video/') ? 'video' : 'image';
      const uploadUrl = `https://api.cloudinary.com/v1_1/${cloudName}/${resourceType}/upload`;

      axios.post(uploadUrl, formData, {
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const progress = (progressEvent.loaded / progressEvent.total) * 100;
            onChange('media', (prev: MediaItem[]) =>
              (Array.isArray(prev) ? prev : media).map(m => 
                m.id === item.id ? { ...m, upload_progress: progress } : m
              )
            );
          }
        }
      }).then(res => {
        const secureUrl = res.data.secure_url;
        
        // Dynamically import mediaService to avoid circular dependencies if any
        import('../../../services/api').then(({ mediaService }) => {
          mediaService.upload({
            hostel: data.hostel_id || null,
            category: item.category,
            file_url: secureUrl,
            mime_type: item.mime_type,
            file_name: item.file_name,
          }).then(backendRes => {
            onChange('media', (prev: MediaItem[]) =>
              (Array.isArray(prev) ? prev : media).map(m => 
                m.id === item.id ? { 
                  ...m, 
                  id: backendRes.id || m.id, // Replace with actual backend UUID
                  upload_progress: 100, 
                  remote_url: secureUrl 
                } : m
              )
            );
          }).catch(err => {
            console.error('Backend link failed:', err);
            alert(`Failed to save ${item.file_name} to database.`);
          });
        });
      }).catch(err => {
        console.error('Upload failed:', err);
        alert(`Failed to upload ${item.file_name} to cloud.`);
      });
    });
  }, [media, onChange]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files, activeCategory);
  }, [activeCategory, addFiles]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) addFiles(e.target.files, activeCategory);
    e.target.value = '';
  };

  const removeMedia = (id: string) => {
    const item = media.find(m => m.id === id);
    // Backend UUIDs are 36 chars long, temporary frontend IDs are 8 chars
    if (item && item.id.length > 10) {
      import('../../../services/api').then(({ mediaService }) => {
        mediaService.delete(item.id).catch(err => {
          console.error('Failed to delete media from backend:', err);
        });
      });
    }
    onChange('media', media.filter(m => m.id !== id));
  };

  const categoryMedia = media.filter(m => m.category === activeCategory);
  const activeCfg = CATEGORY_CONFIG.find(c => c.key === activeCategory)!;

  return (
    <div className="space-y-5 animate-fade-in-up">
      <div>
        <h3 className="text-lg font-bold text-white mb-1">Media Upload</h3>
        <p className="text-[#9A9690] text-sm">Upload images and videos of your hostel.</p>
      </div>

      {/* Category tabs */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {CATEGORY_CONFIG.map(c => (
          <button
            key={c.key}
            type="button"
            onClick={() => setActiveCategory(c.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-[10px] border text-sm font-semibold whitespace-nowrap transition-all flex-shrink-0 ${
              activeCategory === c.key
                ? 'border-[#E8571A] bg-[#E8571A]/10 text-[#E8571A]'
                : 'border-[#2A2A2A] text-[#9A9690] hover:border-[#3A3A3A] hover:text-white'
            }`}
          >
            <span>{c.icon}</span>
            <span>{c.label}</span>
            {media.filter(m => m.category === c.key).length > 0 && (
              <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                activeCategory === c.key ? 'bg-[#E8571A] text-white' : 'bg-[#2A2A2A] text-[#9A9690]'
              }`}>
                {media.filter(m => m.category === c.key).length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-[14px] p-8 text-center cursor-pointer transition-all ${
          dragOver
            ? 'border-[#E8571A] bg-[#E8571A]/10'
            : 'border-[#2A2A2A] hover:border-[#E8571A]/50 hover:bg-[#E8571A]/5'
        }`}
      >
        <div className="text-4xl mb-3">{activeCfg.icon}</div>
        <p className="text-white font-semibold mb-1">
          {dragOver ? 'Drop files here' : `Drop ${activeCfg.label} here`}
        </p>
        <p className="text-[#9A9690] text-sm mb-3">or click to browse</p>
        <span className="text-xs text-[#4A4A4A] font-medium">
          {activeCategory === 'video' ? 'MP4, MOV, AVI up to 100MB' : 'JPG, PNG, WEBP up to 10MB each'}
        </span>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={activeCfg.accept}
          onChange={handleFileInput}
          className="hidden"
        />
      </div>

      {/* Preview grid */}
      {categoryMedia.length > 0 && (
        <div>
          <p className="text-[12px] font-semibold text-[#9A9690] uppercase tracking-wider mb-3">
            {activeCfg.label} ({categoryMedia.length})
          </p>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
            {categoryMedia.map(item => (
              <div key={item.id} className="relative group rounded-[10px] overflow-hidden bg-[#0F0F0F] border border-[#2A2A2A] aspect-square">
                {item.mime_type.startsWith('video/') ? (
                  <div className="w-full h-full flex items-center justify-center text-3xl">🎥</div>
                ) : (
                  <img
                    src={item.preview_url}
                    alt={item.file_name}
                    className="w-full h-full object-cover"
                  />
                )}

                {/* Upload progress overlay */}
                {item.upload_progress < 100 && (
                  <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                    <div className="w-12 h-12 relative">
                      <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                        <circle cx="18" cy="18" r="15" fill="none" stroke="#2A2A2A" strokeWidth="3" />
                        <circle cx="18" cy="18" r="15" fill="none" stroke="#E8571A" strokeWidth="3"
                          strokeDasharray={`${item.upload_progress * 0.94} 94`} strokeLinecap="round" />
                      </svg>
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">
                        {Math.round(item.upload_progress)}%
                      </span>
                    </div>
                  </div>
                )}

                {/* Delete button */}
                <button
                  type="button"
                  onClick={() => removeMedia(item.id)}
                  className="absolute top-1.5 right-1.5 w-6 h-6 bg-red-500 rounded-full flex items-center justify-center text-white shadow-md hover:bg-red-600 transition-colors z-10"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>

                {/* File name tooltip */}
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <p className="text-[9px] text-white truncate font-medium">{item.file_name}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {categoryMedia.length === 0 && (
        <p className="text-center text-[#4A4A4A] text-sm py-2">No {activeCfg.label.toLowerCase()} uploaded yet</p>
      )}
    </div>
  );
};
