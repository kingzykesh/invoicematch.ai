import PropTypes from 'prop-types';

export default function ResultDisplay({ data }) {
  console.log('ResultDisplay data:', data);
  return (
    <div className="space-y-6">
      <div className="p-6 rounded-xl shadow bg-gray-50">
        <h2 className="text-xl font-bold mb-2">Executive Summary</h2>
        <pre className="text-sm whitespace-pre-wrap">{data.executiveSummary}</pre>
      </div>
      <div className="p-6 rounded-xl shadow bg-gray-50">
        <h2 className="text-xl font-bold mb-2">Line Item Breakdown</h2>
        <table className="min-w-full text-sm text-left border border-gray-200 rounded-xl overflow-hidden">
          <thead className="bg-gray-100">
            <tr>
              <th className="px-4 py-2">Description</th>
              <th className="px-4 py-2">Billed</th>
              <th className="px-4 py-2">Paid</th>
              <th className="px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.reconciliation.lineItems.map((item, idx) => (
              <tr key={idx} className="border-t">
                <td className="px-4 py-2">{item.description}</td>
                <td className="px-4 py-2">₦{item.billed.toLocaleString()}</td>
                <td className="px-4 py-2">₦{item.paid.toLocaleString()}</td>
                <td className="px-4 py-2">{item.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

ResultDisplay.propTypes = {
  data: PropTypes.shape({
    executiveSummary: PropTypes.string.isRequired,
    reconciliation: PropTypes.shape({
      lineItems: PropTypes.arrayOf(
        PropTypes.shape({
          description: PropTypes.string.isRequired,
          billed: PropTypes.number.isRequired,
          paid: PropTypes.number.isRequired,
          status: PropTypes.string.isRequired,
        })
      ).isRequired,
    }).isRequired,
  }).isRequired,
};