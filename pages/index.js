import { useState } from 'react';
import { motion } from 'framer-motion';
import FileUpload from '../components/FileUpload';
import ResultDisplay from '../components/ResultDisplay';
import Toast from '../components/Toast';

export default function Home() {
  const [hospitalFile, setHospitalFile] = useState(null);
  const [insurerFile, setInsurerFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [toast, setToast] = useState('');

  const handleReset = () => {
    setHospitalFile(null);
    setInsurerFile(null);
    setResult(null);
    setToast('');
  };

  const handleReconcile = async () => {
    if (!hospitalFile || !insurerFile) {
      const missing = !hospitalFile ? 'Hospital Invoice' : 'Insurer Payout Summary';
      setToast(`Please upload the missing file: ${missing}`);
      return;
    }

    setLoading(true);
    setToast('');
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('hospital_invoice', hospitalFile);
      formData.append('insurer_summary', insurerFile);

      const res = await fetch('/reconcile', {
        method: 'POST',
        body: formData,
      });

      // lets used this debug tool
      console.log('Response status:', res.status);
      const errorText = await res.text();
      console.log('Error body:', errorText);

      if (!res.ok) {
        setToast(`Failed: ${errorText}`);
        return;
      }

      const data = JSON.parse(errorText);
      setResult(data);
    } catch (err) {
      console.error(err);
      setToast('Upload failed, please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-white font-sans">
      {/* Sidebar comes here, i will include logo later */}
      <aside className="w-64 bg-gradient-to-b from-[#2929FF] to-[#C47BFF] text-white p-6 flex flex-col justify-between">
        <div>
          <h2 className="text-xl font-bold">Invoice Match AI</h2>
        </div>
        <div className="text-sm text-center opacity-75">© 2025 Qudus AI</div>
      </aside>

      {/* Main side here*/}
      <main className="flex-1 p-10">
        <div className="max-w-5xl mx-auto pt-10">
          <h1 className="text-4xl font-bold text-center mb-12 bg-gradient-to-r from-[#2929FF] to-[#C47BFF] bg-clip-text text-transparent">
            Invoice Match AI
          </h1>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
            <FileUpload
              label="Hospital Invoice"
              file={hospitalFile}
              setFile={setHospitalFile}
            />
            <FileUpload
              label="Insurer Payout Summary"
              file={insurerFile}
              setFile={setInsurerFile}
            />
          </div>

          <div className="flex items-center gap-6 mb-10">
            <button
              onClick={handleReconcile}
              disabled={loading}
              className="bg-gradient-to-r from-[#2929FF] to-[#C47BFF] text-white px-6 py-2 rounded-xl shadow disabled:opacity-50 flex items-center gap-2"
            >
              {loading && (
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
              )}
              {loading ? 'Reconciling...' : 'Reconcile'}
            </button>
            <button
              onClick={handleReset}
              className="bg-gray-200 text-gray-800 px-4 py-2 rounded-xl"
            >
              Reset
            </button>
          </div>

          {result && <ResultDisplay data={result} />}
          {toast && <Toast message={toast} onClose={() => setToast('')} />}
        </div>
      </main>
    </div>
  );
}
