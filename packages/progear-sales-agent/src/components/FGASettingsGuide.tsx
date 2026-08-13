import { CircleHelp } from 'lucide-react';

export default function FGASettingsGuide() {
  return (
    <section className="overflow-hidden rounded-xl border-2 border-purple-200 bg-white shadow-sm">
      <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-3">
        <h2 className="flex items-center gap-2 font-semibold text-white">
          <CircleHelp className="h-5 w-5" aria-hidden="true" />
          What do these settings mean?
        </h2>
      </div>

      <div className="p-4">
        <div className="overflow-hidden rounded-lg border border-gray-200">
          <table className="w-full text-left text-xs text-gray-700">
            <thead className="border-b border-gray-200 bg-gray-50 text-gray-600">
              <tr>
                <th scope="col" className="w-40 px-3 py-2 font-semibold">
                  Setting
                </th>
                <th scope="col" className="px-3 py-2 font-semibold">
                  What it allows
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              <tr>
                <th scope="row" className="px-3 py-2 font-medium text-gray-800">
                  Clearance 1–2
                </th>
                <td className="px-3 py-2">Inventory reads only; inventory writes are blocked</td>
              </tr>
              <tr>
                <th scope="row" className="px-3 py-2 font-medium text-gray-800">
                  Clearance 3–6
                </th>
                <td className="px-3 py-2">An active manager can update standard inventory</td>
              </tr>
              <tr>
                <th scope="row" className="px-3 py-2 font-medium text-gray-800">
                  Clearance 7–10
                </th>
                <td className="px-3 py-2">
                  An active manager can update standard and classified inventory
                </td>
              </tr>
              <tr>
                <th scope="row" className="px-3 py-2 font-medium text-gray-800">
                  On vacation: False
                </th>
                <td className="px-3 py-2">Inventory access is not blocked by vacation status</td>
              </tr>
              <tr>
                <th scope="row" className="px-3 py-2 font-medium text-gray-800">
                  On vacation: True
                </th>
                <td className="px-3 py-2">
                  All inventory access is blocked due to the user&apos;s vacation status
                </td>
              </tr>
              <tr>
                <th scope="row" className="px-3 py-2 font-medium text-gray-800">
                  <span className="block">Inventory increase:</span>
                  <span className="block whitespace-nowrap">1–499 units</span>
                </th>
                <td className="px-3 py-2">
                  An authorized active manager can update inventory immediately
                </td>
              </tr>
              <tr>
                <th scope="row" className="px-3 py-2 font-medium text-gray-800">
                  <span className="block">Inventory increase:</span>
                  <span className="block whitespace-nowrap">500+ units</span>
                </th>
                <td className="px-3 py-2">
                  Creates an access request that must be approved by the AIAgentOwners group
                </td>
              </tr>
            </tbody>
          </table>
          <p className="border-t border-gray-200 bg-gray-50 px-3 py-2 text-[11px] leading-relaxed text-gray-600">
            Higher clearance includes every level below it. Clearance does not make someone a
            manager; inventory writes still require Manager = True.
          </p>
        </div>
      </div>
    </section>
  );
}
