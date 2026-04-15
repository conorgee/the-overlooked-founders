import { useState } from "react";
import { ArrowRight, ArrowLeft, Upload } from "lucide-react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Textarea } from "../ui/Textarea";
import { supabase } from "../../lib/supabase";
import { useAuth } from "../../lib/auth";
import { SERVICE_URL, apiHeaders } from "../../lib/api";

type Step = 1 | 2 | 3;

export function ApplicationForm() {
  const { user } = useAuth();
  const [step, setStep] = useState<Step>(1);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    email: "",
    businessName: "",
    businessIdea: "",
    stage: "idea",
    videoFile: null as File | null,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const update = (field: string, value: string | File | null) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const validateStep = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (step === 1) {
      if (!form.firstName.trim()) newErrors.firstName = "Required";
      if (!form.lastName.trim()) newErrors.lastName = "Required";
      if (!form.email.trim()) newErrors.email = "Required";
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))
        newErrors.email = "Invalid email";
    }
    if (step === 2) {
      if (!form.businessName.trim()) newErrors.businessName = "Required";
      if (!form.businessIdea.trim()) newErrors.businessIdea = "Required";
      else if (form.businessIdea.trim().length < 50)
        newErrors.businessIdea = "Please write at least 50 characters";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const next = () => {
    if (validateStep()) setStep((s) => Math.min(s + 1, 3) as Step);
  };

  const back = () => setStep((s) => Math.max(s - 1, 1) as Step);

  const submit = async () => {
    setSubmitting(true);
    setSubmitError("");

    try {
      let videoPitchUrl: string | null = null;

      // Upload video to Supabase Storage if provided
      if (form.videoFile) {
        const ext = form.videoFile.name.split(".").pop();
        const path = `pitches/${Date.now()}-${form.firstName.toLowerCase()}.${ext}`;
        const { error: uploadError } = await supabase.storage
          .from("video-pitches")
          .upload(path, form.videoFile);

        if (uploadError) throw new Error(`Video upload failed: ${uploadError.message}`);

        const { data: urlData } = supabase.storage
          .from("video-pitches")
          .getPublicUrl(path);
        videoPitchUrl = urlData.publicUrl;
      }

      // Insert application
      const { data: insertData, error: insertError } = await supabase
        .from("applications")
        .insert({
          user_id: user?.id || null,
          first_name: form.firstName,
          last_name: form.lastName,
          email: form.email,
          business_name: form.businessName,
          business_idea: form.businessIdea,
          stage: form.stage,
          video_pitch_url: videoPitchUrl,
          status: "pending",
        })
        .select("id")
        .single();

      if (insertError) throw new Error(insertError.message);

      // Fire-and-forget: trigger AI scoring
      if (insertData?.id) {
        fetch(`${SERVICE_URL}/score-application`, {
          method: "POST",
          headers: apiHeaders(),
          body: JSON.stringify({ applicationId: insertData.id }),
        }).catch(() => {});
      }

      setSubmitted(true);
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="py-20">
        <p className="text-xs uppercase tracking-[0.2em] text-text-muted mb-6">
          Application Received
        </p>
        <h2 className="text-3xl sm:text-4xl font-medium text-white tracking-[-0.04em] mb-6">
          Thank you, {form.firstName}
        </h2>
        <p className="text-text-muted leading-relaxed max-w-lg">
          We'll review your application and get back to you within 5 business
          days. Keep an eye on {form.email}.
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Progress */}
      <div className="flex items-center gap-3 mb-12">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex-1">
            <div
              className={`h-px transition-colors duration-500 ${
                s <= step ? "bg-white" : "bg-white/10"
              }`}
            />
          </div>
        ))}
      </div>

      {step === 1 && (
        <div className="space-y-8">
          <h3 className="text-2xl font-medium text-white tracking-[-0.02em]">
            About You
          </h3>
          <div className="grid sm:grid-cols-2 gap-8">
            <Input
              label="First Name"
              placeholder="John"
              value={form.firstName}
              onChange={(e) => update("firstName", e.target.value)}
              error={errors.firstName}
            />
            <Input
              label="Last Name"
              placeholder="Doe"
              value={form.lastName}
              onChange={(e) => update("lastName", e.target.value)}
              error={errors.lastName}
            />
          </div>
          <Input
            label="Email"
            type="email"
            placeholder="john@example.com"
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            error={errors.email}
          />
        </div>
      )}

      {step === 2 && (
        <div className="space-y-8">
          <h3 className="text-2xl font-medium text-white tracking-[-0.02em]">
            Your Business
          </h3>
          <Input
            label="Business Name"
            placeholder="My Startup"
            value={form.businessName}
            onChange={(e) => update("businessName", e.target.value)}
            error={errors.businessName}
          />
          <Textarea
            label="Business Idea"
            placeholder="Describe your business idea, the problem you're solving, and who your target customer is..."
            value={form.businessIdea}
            onChange={(e) => update("businessIdea", e.target.value)}
            error={errors.businessIdea}
            rows={5}
          />
          <div className="flex flex-col gap-2">
            <label className="text-xs uppercase tracking-widest text-text-muted font-medium">
              Stage
            </label>
            <select
              value={form.stage}
              onChange={(e) => update("stage", e.target.value)}
              className="bg-transparent border-b border-white/20 px-0 py-3 text-white focus:outline-none focus:border-white transition-colors"
            >
              <option value="idea" className="bg-black">Just an idea</option>
              <option value="mvp" className="bg-black">Building MVP</option>
              <option value="launched" className="bg-black">Launched, early customers</option>
              <option value="growing" className="bg-black">Growing, looking to scale</option>
            </select>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-8">
          <h3 className="text-2xl font-medium text-white tracking-[-0.02em]">
            Video Pitch
          </h3>
          <p className="text-text-muted text-[15px] leading-relaxed">
            Record a 2-minute video telling us about yourself and your business
            idea. Be authentic — we want to hear your story.
          </p>
          <div className="border border-dashed border-white/10 flex flex-col items-center justify-center py-16">
            <Upload className="w-8 h-8 text-text-subtle mb-4" />
            <p className="text-text-muted text-sm mb-1">
              {form.videoFile ? form.videoFile.name : "Drop your video here"}
            </p>
            <p className="text-text-subtle text-xs mb-6">MP4 only. Max 2 minutes.</p>
            <label className="cursor-pointer">
              <Button variant="secondary" size="sm" type="button">
                Choose File
              </Button>
              <input
                type="file"
                accept="video/mp4,.mp4"
                className="hidden"
                onChange={(e) => update("videoFile", e.target.files?.[0] || null)}
              />
            </label>
          </div>
        </div>
      )}

      {submitError && (
        <div className="mt-6 text-sm text-red-400 bg-red-400/10 border border-red-400/20 px-4 py-3">
          {submitError}
        </div>
      )}

      <div className="flex justify-between mt-12">
        {step > 1 ? (
          <Button variant="ghost" onClick={back} disabled={submitting}>
            <ArrowLeft className="w-4 h-4" />
            Back
          </Button>
        ) : (
          <div />
        )}
        {step < 3 ? (
          <Button onClick={next}>
            Next
            <ArrowRight className="w-4 h-4" />
          </Button>
        ) : (
          <Button onClick={submit} disabled={submitting}>
            {submitting ? "Submitting..." : "Submit Application"}
            <ArrowRight className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
