"use client";

import { CampaignImport } from "@/components/campaigns/CampaignImport";
import { CampaignPageHeader } from "@/components/campaigns/CampaignPageHeader";

export default function ImportCampaignPage() {
  return (
    <div className="space-y-6">
      <CampaignPageHeader
        backHref="/campaigns"
        backLabel="Semua campaign"
        title="Import campaign"
        description="Tempel teks dari situs campaign, periksa hasil analisisnya, lalu simpan sebagai campaign yang bisa dipakai berulang."
      />
      <CampaignImport />
    </div>
  );
}
