import { useState } from 'react';
import { motion } from 'framer-motion';
import FileUpload from '../components/FileUpload';
import ResultDisplay from '../components/ResultDisplay';
import Toast from '../components/Toast';
import Image from 'next/image';

const API_URL = `https://invoicematch-ai-4f7em.ondigitalocean.app/reconcile`;

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
      setToast({ message: `Please upload the missing file: ${missing}`, type: 'error' });
      return;
    }

    setLoading(true);
    setToast('');
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('invoice_file', hospitalFile);
      formData.append('payout_summary_file', insurerFile);

      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
        },
        body: formData,
      });

      const json = await response.json();
      if (process.env.NODE_ENV === 'development') {
        console.log('RESPONSE JSON:', json);
      }

      if (!response.ok) {
        setToast({ message: json.status || 'Something went wrong.', type: 'error' });
      } else {
        setResult(json.data);
        setToast({ message: 'Reconciliation successful!', type: 'success' });
      }
    } catch (err) {
      if (process.env.NODE_ENV === 'development') {
        console.error(err);
      }
      setToast({ message: 'Upload failed, please try again.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-white p-6 md:p-10 font-sans">
      <div className="max-w-5xl mx-auto pt-10">
        <div className="flex flex-col items-center mb-6">
          <Image src="/logo.png" alt="Invoice Match AI Logo" width={64} height={64} className="mb-2" />
        </div>
        <h1 className="text-3xl md:text-4xl font-bold text-center mb-12 bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
          Invoice Match AI
        </h1>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8 mb-10">
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

        <div className="flex flex-wrap items-center gap-4 md:gap-6 mb-10">
          <button
            onClick={handleReconcile}
            disabled={loading}
            className="bg-gradient-to-r from-primary to-secondary text-white px-6 py-2 rounded-xl shadow disabled:opacity-50 flex items-center gap-2"
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
        {toast && toast.message && <Toast message={toast.message} type={toast.type} onClose={() => setToast('')} />}
      </div>
    </main>
  );
}
