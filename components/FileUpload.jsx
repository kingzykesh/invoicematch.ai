
export default function FileUpload({ label, file, setFile }) {
  const handleChange = (e) => {
    const uploadedFile = e.target.files[0];
    if (uploadedFile) setFile(uploadedFile);
  };

  return (
    <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center">
      <p className="mb-4 font-semibold">{label}</p>
      <input
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        onChange={handleChange}
        className="mb-2"
      />
      {file && <p className="text-sm text-gray-600">{file.name}</p>}
    </div>
  );
}