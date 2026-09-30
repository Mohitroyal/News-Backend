-- Allow anyone to view posted clippings
CREATE POLICY "Allow public to view posted clippings"
ON public.clippings FOR SELECT
TO authenticated, anon
USING (is_posted = true);
