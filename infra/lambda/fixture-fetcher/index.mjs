export const handler = async (event) => {
  const bucketName = process.env.DATA_BUCKET_NAME
  const apiKeyParameterName = process.env.API_KEY_PARAMETER_NAME

  console.log(
    JSON.stringify({
      message: 'Fixture fetcher scaffold invoked. API integration is not implemented yet.',
      bucketName,
      apiKeyParameterName,
      event,
    }),
  )

  return {
    ok: true,
    published: false,
  }
}
