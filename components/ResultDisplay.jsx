export default function ResultDisplay({ data }) {
  return (
    <div className="space-y-6">
      <div className="p-6 rounded-xl shadow bg-gray-50">
        <h2 className="text-xl font-bold mb-2">Executive Summary</h2>
        <pre className="text-sm whitespace-pre-wrap">{JSON.stringify(data.summary, null, 2)}</pre>
      </div>
      <div className="p-6 rounded-xl shadow bg-gray-50">
        <h2 className="text-xl font-bold mb-2">Line Item Breakdown</h2>
        <pre className="text-sm whitespace-pre-wrap">{JSON.stringify(data.lineItems, null, 2)}</pre>
      </div>
    </div>
  );
}